/**
 * PM2 Ecosystem Configuration for RadioShaq
 * 
 * This configuration manages all RadioShaq services during development
 * and testing using PM2 process manager.
 * 
 * Usage:
 *   pm2 start infrastructure/local/ecosystem.config.js
 *   pm2 logs
 *   pm2 stop all
 *   pm2 delete all
 * 
 * Environment Variables:
 *   - RADIOSHAQ_MODE: 'field' or 'hq' (default: 'field')
 *   - RADIOSHAQ_DEBUG: Enable debug logging (default: 'false')
 *   - RADIOSHAQ_LOG_LEVEL: Log level (default: 'INFO')
 */

const path = require('path');

// Base paths
const cwd = path.resolve(__dirname, '../..');
const logsDir = path.join(cwd, 'logs');

module.exports = {
  apps: [
    // ==========================================
    // RadioShaq API Server (FastAPI)
    // ==========================================
    {
      name: 'radioshaq-api',
      script: 'python',
      args: '-m radioshaq.api.server',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['radioshaq/api', 'radioshaq/config', 'radioshaq/database'],
      ignore_watch: ['__pycache__', '*.pyc', '.git', 'logs', '.pytest_cache'],
      watch_delay: 2000,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'development',
        RADIOSHAQ_MODE: 'field',
        RADIOSHAQ_DEBUG: 'true',
        RADIOSHAQ_LOG_LEVEL: 'DEBUG',
        DATABASE_URL: 'postgresql+asyncpg://radioshaq:radioshaq@localhost:5432/radioshaq',
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
        JWT_ALGORITHM: 'HS256',
        API_HOST: '0.0.0.0',
        API_PORT: '8000',
        RELOAD: 'true',
        // Mistral
        MISTRAL_API_KEY: process.env.MISTRAL_API_KEY || '',
        // AWS (for local testing with localstack if needed)
        AWS_REGION: 'us-east-1',
        AWS_ACCESS_KEY_ID: 'local',
        AWS_SECRET_ACCESS_KEY: 'local',
        DYNAMODB_ENDPOINT: 'http://localhost:4566',
        // Redis (for caching/sessions if needed)
        REDIS_URL: 'redis://localhost:6379/0',
        // Radio (disabled by default for dev)
        RADIO_ENABLED: 'false',
        RADIO_RIG_MODEL: '1',
        RADIO_PORT: '/dev/ttyUSB0',
        // WhatsApp Bridge
        BRIDGE_URL: 'ws://localhost:3001',
        BRIDGE_TOKEN: 'dev-bridge-token',
        // Alembic
        ALEMBIC_CONFIG: 'infrastructure/local/alembic.ini',
        // Memory (per-callsign; optional Hindsight)
        RADIOSHAQ_MEMORY__ENABLED: 'true',
        RADIOSHAQ_MEMORY__HINDSIGHT_BASE_URL: 'http://localhost:8888',
        RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED: 'true',
        RADIOSHAQ_MEMORY__SUMMARY_TIMEZONE: 'America/New_York',
      },
      env_test: {
        NODE_ENV: 'test',
        RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED: 'false',
      },
      env_production: {
        NODE_ENV: 'production',
        RADIOSHAQ_DEBUG: 'false',
        RADIOSHAQ_LOG_LEVEL: 'INFO',
        RELOAD: 'false',
      },
      log_file: path.join(logsDir, 'api.log'),
      out_file: path.join(logsDir, 'api-out.log'),
      error_file: path.join(logsDir, 'api-error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: false,
      time: true,
      // Health monitoring
      min_uptime: '10s',
      max_restarts: 10,
      // PM2 advanced
      kill_timeout: 5000,
      listen_timeout: 8000,
      shutdown_with_message: true,
      wait_ready: true,
      // Custom metrics
      instances_var: 'INSTANCE_ID',
    },

    // ==========================================
    // Hindsight API (optional: when running via pip instead of Docker)
    // Start with: pm2 start ecosystem.config.js --only hindsight-api
    // Requires: pip install hindsight-all; set HINDSIGHT_API_LLM_* in env
    // ==========================================
    {
      name: 'hindsight-api',
      script: 'hindsight-api',
      args: '--port 8888',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      max_memory_restart: '512M',
      env: {
        HINDSIGHT_API_LLM_PROVIDER: process.env.HINDSIGHT_API_LLM_PROVIDER || 'openai',
        HINDSIGHT_API_LLM_API_KEY: process.env.HINDSIGHT_API_LLM_API_KEY || '',
        HINDSIGHT_API_LLM_MODEL: process.env.HINDSIGHT_API_LLM_MODEL || 'gpt-4o-mini',
        // Same Postgres as RadioShaq when running on host (Docker Postgres on 5434)
        HINDSIGHT_API_DATABASE_URL: process.env.HINDSIGHT_API_DATABASE_URL || 'postgresql://radioshaq:radioshaq@127.0.0.1:5434/radioshaq',
        HINDSIGHT_API_DATABASE_SCHEMA: process.env.HINDSIGHT_API_DATABASE_SCHEMA || 'hindsight',
        HINDSIGHT_API_RUN_MIGRATIONS_ON_STARTUP: process.env.HINDSIGHT_API_RUN_MIGRATIONS_ON_STARTUP || 'true',
      },
      log_file: path.join(logsDir, 'hindsight-api.log'),
      out_file: path.join(logsDir, 'hindsight-api-out.log'),
      error_file: path.join(logsDir, 'hindsight-api-error.log'),
    },

    // ==========================================
    // RadioShaq WhatsApp Bridge (Node.js)
    // ==========================================
    {
      name: 'radioshaq-bridge',
      script: 'bridge/dist/index.js',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['bridge/dist'],
      ignore_watch: ['node_modules', 'logs'],
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'development',
        BRIDGE_PORT: '3001',
        BRIDGE_HOST: '127.0.0.1',
        BRIDGE_TOKEN: 'dev-bridge-token',
        LOG_LEVEL: 'debug',
        // WhatsApp Web.js options
        WA_HEADLESS: 'true',
        WA_QR_TIMEOUT: '60000',
        WA_RESTART_ON_AUTH_FAIL: 'true',
        // Puppeteer options
        PUPPETEER_ARGS: '--no-sandbox,--disable-setuid-sandbox',
      },
      env_production: {
        NODE_ENV: 'production',
        LOG_LEVEL: 'info',
        WA_HEADLESS: 'true',
      },
      log_file: path.join(logsDir, 'bridge.log'),
      out_file: path.join(logsDir, 'bridge-out.log'),
      error_file: path.join(logsDir, 'bridge-error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      time: true,
      // Source map support for debugging
      source_map_support: true,
      // Node.js args
      node_args: '--experimental-vm-modules',
    },

    // ==========================================
    // RadioShaq Orchestrator Worker
    // ==========================================
    {
      name: 'radioshaq-orchestrator',
      script: 'python',
      args: '-m radioshaq.orchestrator.worker',
      cwd: cwd,
      instances: 2,
      exec_mode: 'cluster',
      autorestart: true,
      watch: ['radioshaq/orchestrator', 'radioshaq/specialized', 'radioshaq/middleware'],
      ignore_watch: ['__pycache__', '*.pyc', '.git', 'logs', '.pytest_cache'],
      watch_delay: 2000,
      max_memory_restart: '2G',
      env: {
        NODE_ENV: 'development',
        RADIOSHAQ_MODE: 'field',
        RADIOSHAQ_DEBUG: 'true',
        RADIOSHAQ_LOG_LEVEL: 'DEBUG',
        WORKER_TYPE: 'orchestrator',
        DATABASE_URL: 'postgresql+asyncpg://radioshaq:radioshaq@localhost:5432/radioshaq',
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
        MISTRAL_API_KEY: process.env.MISTRAL_API_KEY || '',
        // REACT Loop settings
        REACT_MAX_ITERATIONS: '50',
        REACT_PHASE_TIMEOUT: '300',
        JUDGE_QUALITY_THRESHOLD: '0.7',
        // Middleware
        UPSTREAM_ENABLED: 'true',
        MEMORY_UPSTREAM_BATCH_SIZE: '10',
      },
      env_production: {
        NODE_ENV: 'production',
        RADIOSHAQ_DEBUG: 'false',
        RADIOSHAQ_LOG_LEVEL: 'INFO',
        REACT_MAX_ITERATIONS: '50',
      },
      log_file: path.join(logsDir, 'orchestrator.log'),
      out_file: path.join(logsDir, 'orchestrator-out.log'),
      error_file: path.join(logsDir, 'orchestrator-error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: false,
      time: true,
      min_uptime: '10s',
      max_restarts: 10,
    },

    // ==========================================
    // RadioShaq Radio Interface Worker (optional)
    // ==========================================
    {
      name: 'radioshaq-radio',
      script: 'python',
      args: '-m radioshaq.radio.worker',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: false,  // Don't auto-restart to avoid radio conflicts
      watch: false,  // Don't watch - radio hardware can be sensitive
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'development',
        RADIOSHAQ_MODE: 'field',
        WORKER_TYPE: 'radio',
        RADIO_ENABLED: 'false',  // Disabled by default
        RADIO_RIG_MODEL: '1',
        RADIO_PORT: '/dev/ttyUSB0',
        RADIO_BAUDRATE: '9600',
        RADIO_USE_DAEMON: 'false',
        // FLDIGI settings
        FLDIGI_HOST: 'localhost',
        FLDIGI_PORT: '7362',
        // Packet radio settings
        PACKET_CALLSIGN: 'N0CALL',
        PACKET_SSID: '0',
        PACKET_KISS_HOST: 'localhost',
        PACKET_KISS_PORT: '8001',
      },
      log_file: path.join(logsDir, 'radio.log'),
      out_file: path.join(logsDir, 'radio-out.log'),
      error_file: path.join(logsDir, 'radio-error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      time: true,
    },

    // ==========================================
    // RadioShaq Field Sync Worker (Field Mode)
    // ==========================================
    {
      name: 'radioshaq-field-sync',
      script: 'python',
      args: '-m radioshaq.modes.field_sync',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['radioshaq/modes'],
      ignore_watch: ['__pycache__', '*.pyc'],
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'development',
        RADIOSHAQ_MODE: 'field',
        WORKER_TYPE: 'field_sync',
        DATABASE_URL: 'postgresql+asyncpg://radioshaq:radioshaq@localhost:5432/radioshaq',
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
        // HQ connection
        HQ_BASE_URL: 'https://hq.radioshaq.example.com',
        HQ_WS_URL: 'wss://hq.radioshaq.example.com/ws',
        FIELD_STATION_ID: 'DEV-FIELD-01',
        FIELD_CALLSIGN: 'N0CALL',
        // Sync settings
        SYNC_INTERVAL_SECONDS: '60',
        SYNC_BATCH_SIZE: '100',
        SYNC_MAX_RETRIES: '5',
        SYNC_RETRY_DELAY: '10',
      },
      log_file: path.join(logsDir, 'field-sync.log'),
      out_file: path.join(logsDir, 'field-sync-out.log'),
      error_file: path.join(logsDir, 'field-sync-error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      time: true,
    },

    // ==========================================
    // RadioShaq Alembic Migration Runner
    // ==========================================
    {
      name: 'radioshaq-alembic',
      script: 'python',
      args: '-m alembic.config upgrade head',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: false,
      watch: false,
      one_time: true,  // Run once and exit
      env: {
        ALEMBIC_CONFIG: 'infrastructure/local/alembic.ini',
        DATABASE_URL: 'postgresql+asyncpg://radioshaq:radioshaq@localhost:5432/radioshaq',
      },
      log_file: path.join(logsDir, 'alembic.log'),
      out_file: path.join(logsDir, 'alembic-out.log'),
      error_file: path.join(logsDir, 'alembic-error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      time: true,
      // Disable auto-start - run manually with: pm2 start radioshaq-alembic
      autostart: false,
    },

    // ==========================================
    // RadioShaq Test Runner (for CI/testing)
    // ==========================================
    {
      name: 'radioshaq-test',
      script: 'python',
      args: '-m pytest tests/ -v --tb=short',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: false,
      watch: false,
      one_time: true,
      env: {
        NODE_ENV: 'test',
        RADIOSHAQ_MODE: 'field',
        RADIOSHAQ_DEBUG: 'true',
        DATABASE_URL: 'postgresql+asyncpg://radioshaq:radioshaq@localhost:5432/radioshaq_test',
        JWT_SECRET: 'test-secret',
        PYTEST_CURRENT_TEST: '1',
        // Test-specific settings
        RADIO_ENABLED: 'false',
        BRIDGE_ENABLED: 'false',
        UPSTREAM_ENABLED: 'false',
      },
      log_file: path.join(logsDir, 'test.log'),
      out_file: path.join(logsDir, 'test-out.log'),
      error_file: path.join(logsDir, 'test-error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      time: true,
      autostart: false,  // Run manually with: pm2 start radioshaq-test
      // Exit gracefully after tests
      kill_timeout: 30000,
    },
  ],

  // ==========================================
  // PM2 Deployment Configuration
  // ==========================================
  // For production with local ASR/TTS, use: pip install -e ".[audio]" or pip install -e ".[audio,tts_kokoro]"
  deploy: {
    production: {
      user: 'radioshaq',
      host: ['radioshaq-prod-01', 'radioshaq-prod-02'],
      ref: 'origin/main',
      repo: 'git@github.com:radioshaq/radioshaq.git',
      path: '/opt/radioshaq',
      'pre-deploy-local': '',
      'post-deploy': 'pip install -e . && pm2 startOrRestart infrastructure/local/ecosystem.config.js --env production',
      'pre-setup': '',
      'post-setup': 'pip install -e .',
    },
  },
};
