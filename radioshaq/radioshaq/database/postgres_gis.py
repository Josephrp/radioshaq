"""PostGIS database manager for RadioShaq.

Provides high-level operations for geographic data storage
and spatial queries using SQLAlchemy and PostGIS.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from geoalchemy2.functions import ST_DWithin, ST_GeogFromText
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from radioshaq.database.models import (
    Base,
    CoordinationEvent,
    OperatorLocation,
    RegisteredCallsign,
    SessionState,
    Transcript,
)


class PostGISManager:
    """Manager for PostGIS database operations.
    
    Provides high-level operations for:
    - Database initialization
    - Operator location storage and queries
    - Transcript management
    - Spatial queries (operators within radius, etc.)
    - Coordination event tracking
    
    Example:
        manager = PostGISManager("postgresql+asyncpg://localhost/radioshaq")
        await manager.init_db()
        
        # Store operator location
        loc = await manager.store_operator_location(
            callsign="N0CALL",
            latitude=40.7128,
            longitude=-74.0060,
        )
        location_id = loc["id"]
        
        # Find nearby operators
        nearby = await manager.find_operators_nearby(
            latitude=40.7128,
            longitude=-74.0060,
            radius_meters=50000,  # 50km
        )
    """
    
    def __init__(self, database_url: str):
        """Initialize PostGIS manager.
        
        Args:
            database_url: PostgreSQL connection URL with asyncpg driver
        """
        self.database_url = database_url
        self.engine = create_async_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            echo=False,
        )
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def init_db(self) -> None:
        """Initialize database tables and PostGIS extension.
        
        Creates:
        - PostGIS extension
        - All RadioShaq tables
        - Spatial indexes
        """
        async with self.engine.begin() as conn:
            # Create PostGIS extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
            # Verify PostGIS is available
            result = await conn.execute(text("SELECT PostGIS_Version()"))
            version = result.scalar()
            print(f"PostGIS version: {version}")
    
    async def drop_db(self) -> None:
        """Drop all database tables (use with caution!)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    async def store_operator_location(
        self,
        callsign: str,
        latitude: float,
        longitude: float,
        altitude_meters: float | None = None,
        accuracy_meters: float | None = None,
        source: str = "manual",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Store operator location with GIS data.
        
        Args:
            callsign: Operator callsign
            latitude: Latitude in degrees (WGS 84)
            longitude: Longitude in degrees (WGS 84)
            altitude_meters: Optional altitude
            accuracy_meters: Optional accuracy estimate
            source: Source of location data
            session_id: Optional session reference
            
        Returns:
            Dict with id, callsign, latitude, longitude, source, timestamp, etc. (avoids TOCTOU refetch).
        """
        callsign_upper = callsign.upper()
        async with self.async_session() as session:
            # Create Point geometry in WGS 84
            # Note: PostGIS Point format is (longitude, latitude)
            location = OperatorLocation(
                callsign=callsign_upper,
                location=f"SRID=4326;POINT({longitude} {latitude})",
                altitude_meters=altitude_meters,
                accuracy_meters=accuracy_meters,
                source=source,
                session_id=session_id,
            )
            session.add(location)
            await session.commit()
            await session.refresh(location)
        return {
            "id": location.id,
            "callsign": location.callsign,
            "latitude": latitude,
            "longitude": longitude,
            "altitude_meters": location.altitude_meters,
            "accuracy_meters": location.accuracy_meters,
            "source": location.source,
            "timestamp": location.timestamp.isoformat() if location.timestamp else None,
            "session_id": location.session_id,
        }
    
    async def find_operators_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float,
        max_results: int = 100,
        recent_only: bool = True,
        recent_hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Find operators within radius of a point.
        
        Uses PostGIS ST_DWithin for efficient spatial queries.
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_meters: Search radius in meters
            max_results: Maximum results to return
            recent_only: Only return recent locations
            recent_hours: How recent for "recent_only"
            
        Returns:
            List of operator location dicts with distance
        """
        async with self.async_session() as session:
            # Build point geometry
            point = f"SRID=4326;POINT({longitude} {latitude})"
            
            # Base query (include lat/lon for each operator so callers can map or compute further)
            query = select(
                OperatorLocation.callsign,
                OperatorLocation.timestamp,
                OperatorLocation.altitude_meters,
                OperatorLocation.source,
                OperatorLocation.session_id,
                text("ST_Y(location::geometry)").label("latitude"),
                text("ST_X(location::geometry)").label("longitude"),
                text(
                    "ST_Distance(location::geography, ST_GeogFromText(:point))"
                ).label("distance_meters"),
            ).where(
                # Use PostGIS ST_DWithin for index-optimized search
                ST_DWithin(
                    OperatorLocation.location.cast(None),  # Cast to geography
                    ST_GeogFromText(point),
                    radius_meters,
                )
            )
            
            # Add recent-only filter: use make_interval so recent_hours is a proper bind (no interpolation)
            if recent_only:
                query = query.where(
                    text("timestamp > NOW() - make_interval(hours => :recent_hours)")
                )
            
            # Order by most recent first
            query = query.order_by(OperatorLocation.timestamp.desc())
            query = query.limit(max_results)
            
            # Execute with bound parameters
            params: dict[str, Any] = {"point": point}
            if recent_only:
                params["recent_hours"] = recent_hours
            result = await session.execute(query, params)
            
            return [
                {
                    "callsign": row.callsign,
                    "latitude": float(row.latitude) if row.latitude is not None else None,
                    "longitude": float(row.longitude) if row.longitude is not None else None,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "altitude_meters": row.altitude_meters,
                    "source": row.source,
                    "session_id": row.session_id,
                    "distance_meters": float(row.distance_meters) if row.distance_meters else None,
                }
                for row in result
            ]
    
    async def get_latest_location(
        self,
        callsign: str,
    ) -> dict[str, Any] | None:
        """Get the most recent location for a callsign.
        
        Args:
            callsign: Operator callsign
            
        Returns:
            Location dict or None if not found
        """
        async with self.async_session() as session:
            query = (
                select(OperatorLocation)
                .where(OperatorLocation.callsign == callsign.upper())
                .order_by(OperatorLocation.timestamp.desc())
                .limit(1)
            )
            result = await session.execute(query)
            location = result.scalar_one_or_none()
            
            if location:
                return location.to_dict()
            return None

    async def get_latest_location_decoded(
        self,
        callsign: str,
    ) -> dict[str, Any] | None:
        """Get the most recent location for a callsign with explicit latitude/longitude.

        Returns a dict with id, callsign, latitude, longitude, source, timestamp,
        altitude_meters, accuracy_meters, session_id (no raw geometry).
        """
        async with self.async_session() as session:
            query = text("""
                SELECT id, callsign,
                       ST_Y(location::geometry) AS latitude,
                       ST_X(location::geometry) AS longitude,
                       altitude_meters, accuracy_meters, source, timestamp, session_id
                FROM operator_locations
                WHERE callsign = :callsign
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            result = await session.execute(query, {"callsign": callsign.upper()})
            row = result.first()
            if not row:
                return None
            m = row._mapping
            return {
                "id": m["id"],
                "callsign": m["callsign"],
                "latitude": float(m["latitude"]),
                "longitude": float(m["longitude"]),
                "altitude_meters": m["altitude_meters"],
                "accuracy_meters": m["accuracy_meters"],
                "source": m["source"],
                "timestamp": m["timestamp"].isoformat() if m["timestamp"] else None,
                "session_id": m["session_id"],
            }

    async def store_transcript(
        self,
        session_id: str,
        source_callsign: str,
        frequency_hz: float,
        mode: str,
        transcript_text: str,
        destination_callsign: str | None = None,
        signal_quality: float | None = None,
        operator_location_id: int | None = None,
        metadata: dict | None = None,
        raw_audio_path: str | None = None,
    ) -> int:
        """Store a radio communication transcript.
        
        Args:
            session_id: Session identifier
            source_callsign: Source operator
            frequency_hz: Frequency in Hz
            mode: Operating mode (FM, SSB, PSK31, etc.)
            transcript_text: Message content
            destination_callsign: Optional destination
            signal_quality: Optional quality 0.0-1.0
            operator_location_id: Optional location reference
            metadata: Optional additional data (e.g. band, relay_from_transcript_id)
            raw_audio_path: Optional path to stored audio file
            
        Returns:
            Transcript record ID
        """
        async with self.async_session() as session:
            transcript = Transcript(
                session_id=session_id,
                source_callsign=source_callsign.upper(),
                destination_callsign=destination_callsign.upper() if destination_callsign else None,
                frequency_hz=frequency_hz,
                mode=mode,
                transcript_text=transcript_text,
                signal_quality=signal_quality,
                operator_location_id=operator_location_id,
                extra_data=metadata,
                raw_audio_path=raw_audio_path,
            )
            session.add(transcript)
            await session.commit()
            return transcript.id
    
    async def search_transcripts(
        self,
        callsign: str | None = None,
        frequency_min: float | None = None,
        frequency_max: float | None = None,
        mode: str | None = None,
        since: str | None = None,  # ISO timestamp
        limit: int = 100,
        band: str | None = None,
        destination_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Search transcripts by various criteria.
        
        Args:
            callsign: Filter by source or destination callsign (or destination only if destination_only=True)
            frequency_min: Minimum frequency in Hz
            frequency_max: Maximum frequency in Hz
            mode: Filter by mode
            since: Filter by timestamp (ISO format)
            limit: Maximum results
            band: Filter by band name (extra_data->>'band')
            destination_only: If True and callsign set, only transcripts where destination_callsign == callsign
            
        Returns:
            List of transcript dicts
        """
        async with self.async_session() as session:
            query = select(Transcript)
            
            if callsign:
                callsign_upper = callsign.upper()
                if destination_only:
                    query = query.where(Transcript.destination_callsign == callsign_upper)
                else:
                    query = query.where(
                        (Transcript.source_callsign == callsign_upper)
                        | (Transcript.destination_callsign == callsign_upper)
                    )
            
            if frequency_min is not None:
                query = query.where(Transcript.frequency_hz >= frequency_min)
            
            if frequency_max is not None:
                query = query.where(Transcript.frequency_hz <= frequency_max)
            
            if mode:
                query = query.where(Transcript.mode == mode)
            
            if since:
                try:
                    since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                except ValueError:
                    since_dt = None
                if since_dt is not None:
                    query = query.where(Transcript.timestamp >= since_dt)
            
            if band:
                query = query.where(text("extra_data->>'band' = :band").bindparams(band=band))
            
            query = query.order_by(Transcript.timestamp.desc()).limit(limit)
            
            result = await session.execute(query)
            return [row.to_dict() for row in result.scalars()]

    async def delete_transcripts_older_than(
        self,
        cutoff: datetime,
        *,
        source: str | None = None,
        limit: int = 10_000,
    ) -> int:
        """Delete transcript rows with timestamp < cutoff. Optionally filter by extra_data->>'source'.
        Returns number of rows deleted. Batch size limited by limit."""
        async with self.async_session() as session:
            subq = (
                select(Transcript.id)
                .where(Transcript.timestamp < cutoff)
                .order_by(Transcript.id)
                .limit(limit)
            )
            if source is not None:
                subq = subq.where(text("extra_data->>'source' = :source").bindparams(source=source))
            stmt = delete(Transcript).where(Transcript.id.in_(subq))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def search_pending_relay_deliveries(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return transcripts with deliver_at set, deliver_at <= now, and delivery_status != 'delivered'."""
        async with self.async_session() as session:
            # extra_data->>'deliver_at' present, (delivery_status is null or != 'delivered'), deliver_at <= now
            query = (
                select(Transcript)
                .where(text("extra_data ? 'deliver_at'"))
                .where(
                    (text("extra_data->>'delivery_status' IS NULL"))
                    | (text("extra_data->>'delivery_status' != 'delivered'"))
                )
                .where(text("(extra_data->>'deliver_at')::timestamptz <= now()"))
                .order_by(text("(extra_data->>'deliver_at')::timestamptz ASC"))
                .limit(limit)
            )
            result = await session.execute(query)
            return [row.to_dict() for row in result.scalars()]

    async def mark_transcript_delivery_done(self, transcript_id: int) -> bool:
        """Set delivery_status to 'delivered' and delivered_at to now in extra_data. Returns True if updated."""
        async with self.async_session() as session:
            result = await session.execute(select(Transcript).where(Transcript.id == transcript_id))
            row = result.scalar_one_or_none()
            if not row:
                return False
            extra = dict(row.extra_data or {})
            extra["delivery_status"] = "delivered"
            extra["delivered_at"] = datetime.now(timezone.utc).isoformat()
            row.extra_data = extra
            await session.commit()
            return True
    
    async def store_coordination_event(
        self,
        event_type: str,
        initiator_callsign: str,
        target_callsign: str | None = None,
        scheduled_time: str | None = None,  # ISO format
        frequency_hz: float | None = None,
        mode: str | None = None,
        status: str = "pending",
        priority: int = 5,
        notes: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        task_id: str | None = None,
        extra_data: dict | None = None,
    ) -> int:
        """Store a coordination event.
        
        Args:
            event_type: Type of event (schedule, relay, emergency)
            initiator_callsign: Initiating operator
            target_callsign: Target operator (if any)
            scheduled_time: Scheduled time (ISO format)
            frequency_hz: Planned frequency
            mode: Planned mode
            status: Event status
            priority: Priority 1-10 (lower = higher)
            notes: Additional notes
            latitude: Optional meeting point latitude
            longitude: Optional meeting point longitude
            task_id: Optional orchestrator task ID
            extra_data: Optional JSON (e.g. emergency_contact_phone, emergency_contact_channel, approved_by, sent_at)
            
        Returns:
            Event record ID
        """
        async with self.async_session() as session:
            event = CoordinationEvent(
                event_type=event_type,
                initiator_callsign=initiator_callsign.upper(),
                target_callsign=target_callsign.upper() if target_callsign else None,
                scheduled_time=scheduled_time,
                frequency_hz=frequency_hz,
                mode=mode,
                status=status,
                priority=priority,
                notes=notes,
                location=f"SRID=4326;POINT({longitude} {latitude})" if latitude is not None and longitude is not None else None,
                task_id=task_id,
                extra_data=extra_data,
            )
            session.add(event)
            await session.commit()
            return event.id

    async def get_coordination_event_by_id(self, event_id: int) -> dict[str, Any] | None:
        """Get a single coordination event by id. Returns None if not found."""
        async with self.async_session() as session:
            result = await session.execute(select(CoordinationEvent).where(CoordinationEvent.id == event_id))
            row = result.scalar_one_or_none()
            return row.to_dict() if row else None

    async def update_coordination_event(
        self,
        event_id: int,
        *,
        status: str | None = None,
        extra_data: dict | None = None,
    ) -> bool:
        """Update a coordination event's status and/or extra_data. Returns True if updated."""
        async with self.async_session() as session:
            result = await session.execute(select(CoordinationEvent).where(CoordinationEvent.id == event_id))
            row = result.scalar_one_or_none()
            if not row:
                return False
            if status is not None:
                row.status = status
            if extra_data is not None:
                existing = dict(row.extra_data or {})
                existing.update(extra_data)
                row.extra_data = existing
            await session.commit()
            return True

    async def claim_emergency_event_pending(self, event_id: int) -> int | None:
        """
        Atomically set status to 'approving' only when status is 'pending'.
        Returns event_id if claimed, None if already processed or not found.
        Prevents TOCTOU: only one concurrent approval can succeed.
        """
        async with self.async_session() as session:
            stmt = (
                update(CoordinationEvent)
                .where(
                    CoordinationEvent.id == event_id,
                    CoordinationEvent.status == "pending",
                )
                .values(status="approving")
                .returning(CoordinationEvent.id)
            )
            result = await session.execute(stmt)
            row = result.one_or_none()
            await session.commit()
            return row[0] if row else None

    async def get_pending_coordination_events(
        self,
        callsign: str | None = None,
        event_type: str | None = None,
        max_results: int = 100,
        status: str | None = "pending",
    ) -> list[dict[str, Any]]:
        """Get coordination events, optionally filtered by status.
        
        Args:
            callsign: Filter by callsign (initiator or target)
            event_type: Filter by event_type (e.g. emergency)
            max_results: Maximum results
            status: Filter by status (default "pending"). Pass None to get all statuses.
            
        Returns:
            List of event dicts
        """
        async with self.async_session() as session:
            query = (
                select(CoordinationEvent)
                .order_by(CoordinationEvent.priority, CoordinationEvent.scheduled_time)
                .limit(max_results)
            )
            if status is not None:
                query = query.where(CoordinationEvent.status == status)
            if callsign:
                callsign_upper = callsign.upper()
                query = query.where(
                    (CoordinationEvent.initiator_callsign == callsign_upper)
                    | (CoordinationEvent.target_callsign == callsign_upper)
                )
            if event_type:
                query = query.where(CoordinationEvent.event_type == event_type)
            
            result = await session.execute(query)
            return [row.to_dict() for row in result.scalars()]
    
    async def save_session_state(
        self,
        session_id: str,
        task_id: str,
        phase: str,
        state_data: dict,
        status: str = "active",
    ) -> None:
        """Save REACT orchestrator session state.
        
        Args:
            session_id: Unique session identifier
            task_id: Task identifier
            phase: Current REACT phase
            state_data: Serialized state
            status: Session status
        """
        async with self.async_session() as session:
            # Check for existing
            result = await session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.phase = phase
                existing.state_data = state_data
                existing.status = status
                if status in ("completed", "failed"):
                    from datetime import datetime
                    existing.completed_at = datetime.utcnow()
            else:
                new_state = SessionState(
                    session_id=session_id,
                    task_id=task_id,
                    phase=phase,
                    state_data=state_data,
                    status=status,
                )
                session.add(new_state)
            
            await session.commit()
    
    async def get_session_state(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve saved session state.
        
        Args:
            session_id: Session identifier
            
        Returns:
            State dict or None if not found
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(SessionState).where(SessionState.session_id == session_id)
            )
            state = result.scalar_one_or_none()
            
            if state:
                return {
                    "session_id": state.session_id,
                    "task_id": state.task_id,
                    "phase": state.phase,
                    "state_data": state.state_data,
                    "status": state.status,
                    "created_at": state.created_at.isoformat() if state.created_at else None,
                    "updated_at": state.updated_at.isoformat() if state.updated_at else None,
                }
            return None

    # -------------------------------------------------------------------------
    # Registered callsigns (whitelist)
    # -------------------------------------------------------------------------

    async def list_registered_callsigns(self) -> list[dict[str, Any]]:
        """List all registered callsigns, newest first."""
        async with self.async_session() as session:
            result = await session.execute(
                select(RegisteredCallsign).order_by(RegisteredCallsign.created_at.desc())
            )
            return [row.to_dict() for row in result.scalars()]

    async def register_callsign(
        self,
        callsign: str,
        source: str = "api",
        preferred_bands: list[str] | None = None,
    ) -> int:
        """Register a callsign. If already present, return its id. Returns new or existing id."""
        normalized = callsign.strip().upper()
        if not normalized:
            raise ValueError("callsign cannot be empty")
        async with self.async_session() as session:
            existing = await session.execute(
                select(RegisteredCallsign).where(RegisteredCallsign.callsign == normalized)
            )
            row = existing.scalar_one_or_none()
            if row:
                if preferred_bands is not None:
                    row.preferred_bands = preferred_bands
                    await session.commit()
                return row.id
            rec = RegisteredCallsign(
                callsign=normalized,
                source=source,
                preferred_bands=preferred_bands,
            )
            session.add(rec)
            await session.commit()
            await session.refresh(rec)
            return rec.id

    async def update_callsign_last_band(self, callsign: str, band: str) -> bool:
        """Set last_band for a registered callsign. Returns True if updated."""
        normalized = callsign.strip().upper()
        band = (band or "").strip() or None
        if not normalized:
            return False
        async with self.async_session() as session:
            result = await session.execute(
                select(RegisteredCallsign).where(RegisteredCallsign.callsign == normalized)
            )
            row = result.scalar_one_or_none()
            if not row:
                return False
            row.last_band = band
            await session.commit()
            return True

    async def update_callsign_preferred_bands(self, callsign: str, preferred_bands: list[str]) -> bool:
        """Set preferred_bands for a registered callsign. Returns True if updated."""
        normalized = callsign.strip().upper()
        if not normalized:
            return False
        bands = [b.strip() for b in preferred_bands if isinstance(b, str) and b.strip()]
        async with self.async_session() as session:
            result = await session.execute(
                select(RegisteredCallsign).where(RegisteredCallsign.callsign == normalized)
            )
            row = result.scalar_one_or_none()
            if not row:
                return False
            row.preferred_bands = bands if bands else None
            await session.commit()
            return True

    async def get_contact_preferences(self, callsign: str) -> dict[str, Any] | None:
        """Get contact preferences for a registered callsign. Returns None if not found."""
        normalized = callsign.strip().upper()
        if not normalized:
            return None
        async with self.async_session() as session:
            result = await session.execute(
                select(RegisteredCallsign).where(RegisteredCallsign.callsign == normalized)
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            # Per-channel opt-out; legacy notify_opt_out_at treats as both channels opted out
            opt_out_sms = row.notify_opt_out_at_sms or row.notify_opt_out_at
            opt_out_wa = row.notify_opt_out_at_whatsapp or row.notify_opt_out_at
            return {
                "callsign": row.callsign,
                "notify_sms_phone": row.notify_sms_phone,
                "notify_whatsapp_phone": row.notify_whatsapp_phone,
                "notify_on_relay": row.notify_on_relay,
                "notify_consent_at": row.notify_consent_at.isoformat() if row.notify_consent_at else None,
                "notify_consent_source": row.notify_consent_source,
                "notify_opt_out_at": row.notify_opt_out_at.isoformat() if row.notify_opt_out_at else None,
                "notify_opt_out_at_sms": opt_out_sms.isoformat() if opt_out_sms else None,
                "notify_opt_out_at_whatsapp": opt_out_wa.isoformat() if opt_out_wa else None,
            }

    async def set_contact_preferences(
        self,
        callsign: str,
        *,
        notify_sms_phone: str | None = None,
        notify_whatsapp_phone: str | None = None,
        notify_on_relay: bool | None = None,
        consent_at: datetime | None = None,
        consent_source: str | None = None,
    ) -> bool:
        """Set contact preferences for a registered callsign. Returns True if updated."""
        normalized = callsign.strip().upper()
        if not normalized:
            return False
        async with self.async_session() as session:
            result = await session.execute(
                select(RegisteredCallsign).where(RegisteredCallsign.callsign == normalized)
            )
            row = result.scalar_one_or_none()
            if not row:
                return False
            if notify_sms_phone is not None:
                row.notify_sms_phone = notify_sms_phone.strip() or None
                if row.notify_sms_phone:
                    row.notify_opt_out_at_sms = None  # Re-enabling SMS clears opt-out for that channel
            if notify_whatsapp_phone is not None:
                row.notify_whatsapp_phone = notify_whatsapp_phone.strip() or None
                if row.notify_whatsapp_phone:
                    row.notify_opt_out_at_whatsapp = None  # Re-enabling WhatsApp clears opt-out for that channel
            if notify_on_relay is not None:
                row.notify_on_relay = notify_on_relay
            if consent_at is not None:
                row.notify_consent_at = consent_at
            if consent_source is not None:
                row.notify_consent_source = consent_source.strip() or None
            await session.commit()
            return True

    async def record_opt_out(self, callsign: str, channel: str) -> bool:
        """Record opt-out for a callsign (channel 'sms' or 'whatsapp'). Clears that channel's phone and sets per-channel opt_out_at. Returns True if updated."""
        normalized = callsign.strip().upper()
        if not normalized or channel not in ("sms", "whatsapp"):
            return False
        async with self.async_session() as session:
            result = await session.execute(
                select(RegisteredCallsign).where(RegisteredCallsign.callsign == normalized)
            )
            row = result.scalar_one_or_none()
            if not row:
                return False
            now = datetime.now(timezone.utc)
            if channel == "sms":
                row.notify_opt_out_at_sms = now
                row.notify_sms_phone = None
            else:
                row.notify_opt_out_at_whatsapp = now
                row.notify_whatsapp_phone = None
            await session.commit()
            return True

    async def record_opt_out_by_phone(self, phone: str, channel: str) -> bool:
        """Record opt-out by phone number. Opts out all callsigns with this phone. Returns True if at least one row was updated."""
        phone = (phone or "").strip()
        if not phone or channel not in ("sms", "whatsapp"):
            return False
        async with self.async_session() as session:
            col = RegisteredCallsign.notify_sms_phone if channel == "sms" else RegisteredCallsign.notify_whatsapp_phone
            opt_out_col = (
                RegisteredCallsign.notify_opt_out_at_sms if channel == "sms" else RegisteredCallsign.notify_opt_out_at_whatsapp
            )
            now = datetime.now(timezone.utc)
            stmt = (
                update(RegisteredCallsign)
                .where(col == phone)
                .values({opt_out_col: now, col: None})
                .returning(RegisteredCallsign.id)
            )
            result = await session.execute(stmt)
            updated_ids = result.scalars().all()
            await session.commit()
            return len(updated_ids) > 0

    async def unregister_callsign(self, callsign: str) -> bool:
        """Remove a callsign from the registry. Returns True if a row was deleted."""
        normalized = callsign.strip().upper()
        async with self.async_session() as session:
            result = await session.execute(delete(RegisteredCallsign).where(RegisteredCallsign.callsign == normalized))
            await session.commit()
            return result.rowcount > 0

    async def is_callsign_registered(self, callsign: str) -> bool:
        """Return True if callsign is in the registry."""
        normalized = callsign.strip().upper()
        async with self.async_session() as session:
            result = await session.execute(
                select(RegisteredCallsign).where(RegisteredCallsign.callsign == normalized)
            )
            return result.scalar_one_or_none() is not None

    async def get_transcript_by_id(self, transcript_id: int) -> dict[str, Any] | None:
        """Load a single transcript by id. Returns None if not found."""
        async with self.async_session() as session:
            result = await session.execute(select(Transcript).where(Transcript.id == transcript_id))
            row = result.scalar_one_or_none()
            return row.to_dict() if row else None
    
    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()
