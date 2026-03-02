/**
 * PM2 Ecosystem Configuration for SHAKODS
 * 
 * This configuration manages all SHAKODS services during development
 * and testing using PM2 process manager.
 * 
 * Usage:
 *   pm2 start infrastructure/local/ecosystem.config.js
 *   pm2 logs
 *   pm2 stop all
 *   pm2 delete all
 * 
 * Environment Variables:
 *   - SHAKODS_MODE: 'field' or 'hq' (default: 'field')
 *   - SHAKODS_DEBUG: Enable debug logging (default: 'false')
 *   - SHAKODS_LOG_LEVEL: Log level (default: 'INFO')
 */

const path = require('path');

// Base paths
const cwd = path.resolve(__dirname, '../..');
const logsDir = path.join(cwd, 'logs');

module.exports = {
  apps: [
    // ==========================================
    // SHAKODS API Server (FastAPI)
    // ==========================================
    {
      name: 'shakods-api',
      script: 'python',
      args: '-m shakods.api.server',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['shakods/api', 'shakods/config', 'shakods/database'],
      ignore_watch: ['__pycache__', '*.pyc', '.git', 'logs', '.pytest_cache'],
      watch_delay: 2000,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'development',
        SHAKODS_MODE: 'field',
        SHAKODS_DEBUG: 'true',
        SHAKODS_LOG_LEVEL: 'DEBUG',
        DATABASE_URL: 'postgresql+asyncpg://shakods:shakods@localhost:5432/shakods',
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
      },
      env_production: {
        NODE_ENV: 'production',
        SHAKODS_DEBUG: 'false',
        SHAKODS_LOG_LEVEL: 'INFO',
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
    // SHAKODS WhatsApp Bridge (Node.js)
    // ==========================================
    {
      name: 'shakods-bridge',
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
    // SHAKODS Orchestrator Worker
    // ==========================================
    {
      name: 'shakods-orchestrator',
      script: 'python',
      args: '-m shakods.orchestrator.worker',
      cwd: cwd,
      instances: 2,
      exec_mode: 'cluster',
      autorestart: true,
      watch: ['shakods/orchestrator', 'shakods/specialized', 'shakods/middleware'],
      ignore_watch: ['__pycache__', '*.pyc', '.git', 'logs', '.pytest_cache'],
      watch_delay: 2000,
      max_memory_restart: '2G',
      env: {
        NODE_ENV: 'development',
        SHAKODS_MODE: 'field',
        SHAKODS_DEBUG: 'true',
        SHAKODS_LOG_LEVEL: 'DEBUG',
        WORKER_TYPE: 'orchestrator',
        DATABASE_URL: 'postgresql+asyncpg://shakods:shakods@localhost:5432/shakods',
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
        SHAKODS_DEBUG: 'false',
        SHAKODS_LOG_LEVEL: 'INFO',
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
    // SHAKODS Radio Interface Worker (optional)
    // ==========================================
    {
      name: 'shakods-radio',
      script: 'python',
      args: '-m shakods.radio.worker',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: false,  // Don't auto-restart to avoid radio conflicts
      watch: false,  // Don't watch - radio hardware can be sensitive
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'development',
        SHAKODS_MODE: 'field',
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
    // SHAKODS Field Sync Worker (Field Mode)
    // ==========================================
    {
      name: 'shakods-field-sync',
      script: 'python',
      args: '-m shakods.modes.field_sync',
      cwd: cwd,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['shakods/modes'],
      ignore_watch: ['__pycache__', '*.pyc'],
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'development',
        SHAKODS_MODE: 'field',
        WORKER_TYPE: 'field_sync',
        DATABASE_URL: 'postgresql+asyncpg://shakods:shakods@localhost:5432/shakods',
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
        // HQ connection
        HQ_BASE_URL: 'https://hq.shakods.example.com',
        HQ_WS_URL: 'wss://hq.shakods.example.com/ws',
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
    // SHAKODS Alembic Migration Runner
    // ==========================================
    {
      name: 'shakods-alembic',
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
        DATABASE_URL: 'postgresql+asyncpg://shakods:shakods@localhost:5432/shakods',
      },
      log_file: path.join(logsDir, 'alembic.log'),
      out_file: path.join(logsDir, 'alembic-out.log'),
      error_file: path.join(logsDir, 'alembic-error.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      time: true,
      // Disable auto-start - run manually with: pm2 start shakods-alembic
      autostart: false,
    },

    // ==========================================
    // SHAKODS Test Runner (for CI/testing)
    // ==========================================
    {
      name: 'shakods-test',
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
        SHAKODS_MODE: 'field',
        SHAKODS_DEBUG: 'true',
        DATABASE_URL: 'postgresql+asyncpg://shakods:shakods@localhost:5432/shakods_test',
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
      autostart: false,  // Run manually with: pm2 start shakods-test
      // Exit gracefully after tests
      kill_timeout: 30000,
    },
  ],

  // ==========================================
  // PM2 Deployment Configuration
  // ==========================================
  deploy: {
    production: {
      user: 'shakods',
      host: ['shakods-prod-01', 'shakods-prod-02'],
      ref: 'origin/main',
      repo: 'git@github.com:shakods/shakods.git',
      path: '/opt/shakods',
      'pre-deploy-local': '',
      'post-deploy': 'pip install -e . && pm2 startOrRestart infrastructure/local/ecosystem.config.js --env production',
      'pre-setup': '',
      'post-setup': 'pip install -e .',
    },
  },
};
