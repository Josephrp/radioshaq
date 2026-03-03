import React from 'react';
import type { PendingResponse } from '../../types/audio';
import { PendingResponseStatus } from '../../types/audio';
import { approvePendingResponse, rejectPendingResponse } from '../../services/shakodsApi';

interface ConfirmationQueueProps {
  pending: PendingResponse[];
  onRefresh: () => void;
  loading?: boolean;
}

export function ConfirmationQueue({ pending, onRefresh, loading }: ConfirmationQueueProps) {
  const [rejecting, setRejecting] = React.useState<string | null>(null);
  const [approving, setApproving] = React.useState<string | null>(null);

  const handleApprove = async (id: string) => {
    setApproving(id);
    try {
      await approvePendingResponse(id);
      onRefresh();
    } finally {
      setApproving(null);
    }
  };

  const handleReject = async (id: string) => {
    setRejecting(id);
    try {
      await rejectPendingResponse(id);
      onRefresh();
    } finally {
      setRejecting(null);
    }
  };

  if (loading) return <p>Loading pending responses…</p>;
  if (pending.length === 0) return <p>No pending responses.</p>;

  return (
    <div className="confirmation-queue">
      <h3>Pending responses ({pending.length})</h3>
      <ul>
        {pending.map((p) => (
          <li key={p.id} data-status={p.status}>
            <div className="pending-transcript">{p.incoming_transcript}</div>
            <div className="pending-proposed">→ {p.proposed_message}</div>
            <div className="pending-actions">
              <button
                type="button"
                onClick={() => handleApprove(p.id)}
                disabled={approving === p.id || p.status !== PendingResponseStatus.PENDING}
              >
                {approving === p.id ? 'Sending…' : 'Approve & send'}
              </button>
              <button
                type="button"
                onClick={() => handleReject(p.id)}
                disabled={rejecting === p.id || p.status !== PendingResponseStatus.PENDING}
              >
                {rejecting === p.id ? 'Rejecting…' : 'Reject'}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
