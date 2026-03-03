/**
 * PM2 Ecosystem Configuration for RadioShaq
 * 
 * This configuration manages all processes for development, testing,
 * and local debugging of the RadioShaq system.
 * 
 * Usage:
 *   pm2 start ecosystem.config.js                      # Start all apps
 *   pm2 start ecosystem.config.js --only radioshaq-api # Start specific app
 *   pm2 start ecosystem.config.js --env test           # Start in test mode
 *   pm2 logs                                           # View all logs
 *   pm2 logs radioshaq-api                             # View specific app logs
 *   pm2 monit                                          # Monitor processes
 */

const path = require('path');
const homedir = require('os').homedir();

// Use project venv Python so PM2 runs the correct interpreter
const venvPython = path.join(__dirname, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin', 'python' + (process.platform === 'win32' ? '.exe' : ''));

module.exports = {
  apps: [
    // =====================================================
    // Main RadioShaq API Server
    // =====================================================
    {
      name: 'radioshaq-api',
      script: require('fs').existsSync(venvPython) ? venvPython : 'python',
      args: ['-m', 'radioshaq.api.server'],
      cwd: __dirname,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['radioshaq/api', 'radioshaq/config', 'radioshaq/database'],
      ignore_watch: ['__pycache__', '*.pyc', '.git', 'logs', '.pytest_cache'],
      max_memory_restart: '512M',
      
      // Environment variables
      env: {
        NODE_ENV: 'development',
        RADIOSHAQ_MODE: 'field',
        RADIOSHAQ_LOG_LEVEL: 'DEBUG',
        RADIOSHAQ_API_HOST: '0.0.0.0',
        RADIOSHAQ_API_PORT: '8000',
        API_PORT: '8000',
        DATABASE_URL: `postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq`,
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
        JWT_ALGORITHM: 'HS256',
        MISTRAL_API_KEY: process.env.MISTRAL_API_KEY || '',
        // Radio configuration
        RADIO_ENABLED: 'false',
        RADIO_RIG_MODEL: '1',
        RADIO_PORT: '/dev/ttyUSB0',
        // Bridge configuration
        BRIDGE_ENABLED: 'true',
        BRIDGE_PORT: '3001',
        // PM2 specific
        PM2_LOG_DATE_FORMAT: 'YYYY-MM-DD HH:mm:ss.SSS',
      },
      
      // Test environment
      env_test: {
        NODE_ENV: 'test',
        RADIOSHAQ_MODE: 'field',
        RADIOSHAQ_LOG_LEVEL: 'DEBUG',
        RADIOSHAQ_API_HOST: '127.0.0.1',
        RADIOSHAQ_API_PORT: '8001',
        API_PORT: '8001',
        DATABASE_URL: `postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq_test`,
        JWT_SECRET: 'test-secret',
        RADIO_ENABLED: 'false',
        BRIDGE_ENABLED: 'false',
      },
      
      // Production-like local environment
      env_production: {
        NODE_ENV: 'production',
        RADIOSHAQ_MODE: 'hq',
        RADIOSHAQ_LOG_LEVEL: 'INFO',
        RADIOSHAQ_API_HOST: '0.0.0.0',
        RADIOSHAQ_API_PORT: '8000',
        DATABASE_URL: process.env.DATABASE_URL || `postgresql://radioshaq:radioshaq@localhost:5432/radioshaq`,
        JWT_SECRET: process.env.JWT_SECRET || '',
        RADIO_ENABLED: process.env.RADIO_ENABLED || 'false',
        BRIDGE_ENABLED: process.env.BRIDGE_ENABLED || 'true',
      },
      
      // Logging
      log_file: './logs/api-combined.log',
      out_file: './logs/api-out.log',
      error_file: './logs/api-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss.SSS Z',
      merge_logs: true,
      
      // Error handling
      min_uptime: '10s',
      max_restarts: 5,
      restart_delay: 3000,
      
      // Health monitoring
      kill_timeout: 5000,
      listen_timeout: 10000,
      
      // Source map support for debugging
      source_map_support: true,
    },
    
    // =====================================================
    // WhatsApp Bridge (Node.js)
    // =====================================================
    {
      name: 'radioshaq-bridge',
      script: './bridge/dist/index.js',
      cwd: __dirname,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,  // Bridge is built, not watched
      max_memory_restart: '256M',
      
      env: {
        NODE_ENV: 'development',
        BRIDGE_PORT: '3001',
        BRIDGE_HOST: '127.0.0.1',
        BRIDGE_AUTH_TOKEN: 'dev-bridge-token',
        LOG_LEVEL: 'debug',
      },
      
      env_test: {
        NODE_ENV: 'test',
        BRIDGE_PORT: '3002',
        BRIDGE_HOST: '127.0.0.1',
        LOG_LEVEL: 'warn',
      },
      
      env_production: {
        NODE_ENV: 'production',
        BRIDGE_PORT: process.env.BRIDGE_PORT || '3001',
        BRIDGE_HOST: process.env.BRIDGE_HOST || '127.0.0.1',
        BRIDGE_AUTH_TOKEN: process.env.BRIDGE_AUTH_TOKEN || '',
        LOG_LEVEL: 'info',
      },
      
      log_file: './logs/bridge-combined.log',
      out_file: './logs/bridge-out.log',
      error_file: './logs/bridge-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss.SSS Z',
      merge_logs: true,
      
      // Bridge is TypeScript-built, restart on source changes if in dev
      watch_options: {
        followSymlinks: false,
      },
      
      min_uptime: '10s',
      max_restarts: 5,
      restart_delay: 5000,
    },
    
    // =====================================================
    // REACT Orchestrator Worker
    // =====================================================
    {
      name: 'radioshaq-orchestrator',
      script: 'python -m radioshaq.orchestrator.worker',
      cwd: __dirname,
      instances: 2,  // Run 2 orchestrator workers in cluster mode
      exec_mode: 'cluster',
      autorestart: true,
      watch: ['radioshaq/orchestrator', 'radioshaq/specialized', 'radioshaq/prompts'],
      ignore_watch: ['__pycache__', '*.pyc', '.git', 'logs'],
      max_memory_restart: '1G',
      
      env: {
        NODE_ENV: 'development',
        WORKER_TYPE: 'orchestrator',
        RADIOSHAQ_LOG_LEVEL: 'DEBUG',
        ORCHESTRATOR_MAX_ITERATIONS: '50',
        ORCHESTRATOR_TIMEOUT_SECONDS: '300',
        DATABASE_URL: `postgresql://radioshaq:radioshaq@localhost:5432/radioshaq`,
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
        REDIS_URL: process.env.REDIS_URL || '',  // For distributed state if needed
      },
      
      env_test: {
        NODE_ENV: 'test',
        WORKER_TYPE: 'orchestrator',
        RADIOSHAQ_LOG_LEVEL: 'WARNING',
        ORCHESTRATOR_MAX_ITERATIONS: '10',
        ORCHESTRATOR_TIMEOUT_SECONDS: '60',
        DATABASE_URL: `postgresql://radioshaq:radioshaq@localhost:5432/radioshaq_test`,
        JWT_SECRET: 'test-secret',
      },
      
      env_production: {
        NODE_ENV: 'production',
        WORKER_TYPE: 'orchestrator',
        RADIOSHAQ_LOG_LEVEL: 'INFO',
        ORCHESTRATOR_MAX_ITERATIONS: '100',
        ORCHESTRATOR_TIMEOUT_SECONDS: '600',
        instances: 4,  // More workers in production
      },
      
      log_file: './logs/orchestrator-combined.log',
      out_file: './logs/orchestrator-out.log',
      error_file: './logs/orchestrator-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss.SSS Z',
      merge_logs: true,
      
      min_uptime: '30s',
      max_restarts: 10,
      restart_delay: 5000,
    },
    
    // =====================================================
    // Message Queue Worker (for async processing)
    // =====================================================
    {
      name: 'radioshaq-mq-worker',
      script: 'python -m radioshaq.mq.worker',
      cwd: __dirname,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['radioshaq/mq', 'radioshaq/channels'],
      ignore_watch: ['__pycache__', '*.pyc'],
      max_memory_restart: '512M',
      
      env: {
        NODE_ENV: 'development',
        WORKER_TYPE: 'mq',
        RADIOSHAQ_LOG_LEVEL: 'DEBUG',
        DATABASE_URL: `postgresql://radioshaq:radioshaq@localhost:5432/radioshaq`,
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
      },
      
      env_test: {
        NODE_ENV: 'test',
        WORKER_TYPE: 'mq',
        RADIOSHAQ_LOG_LEVEL: 'WARNING',
      },
      
      log_file: './logs/mq-worker-combined.log',
      out_file: './logs/mq-worker-out.log',
      error_file: './logs/mq-worker-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss.SSS Z',
      merge_logs: true,
      
      min_uptime: '10s',
      max_restarts: 5,
    },
    
    // =====================================================
    // Database Migration Runner (Alembic)
    // =====================================================
    {
      name: 'radioshaq-migrate',
      script: 'alembic upgrade head',
      cwd: __dirname,
      instances: 1,
      exec_mode: 'fork',
      autorestart: false,  // One-shot migration
      watch: false,
      
      env: {
        NODE_ENV: 'development',
        ALEMBIC_CONFIG: './alembic.ini',
        DATABASE_URL: `postgresql://radioshaq:radioshaq@localhost:5432/radioshaq`,
      },
      
      env_test: {
        NODE_ENV: 'test',
        DATABASE_URL: `postgresql://radioshaq:radioshaq@localhost:5432/radioshaq_test`,
      },
      
      log_file: './logs/migrate-combined.log',
      out_file: './logs/migrate-out.log',
      error_file: './logs/migrate-error.log',
      
      // Run migrations before starting other services
      wait_ready: true,
      listen_timeout: 30000,
    },

    // =====================================================
    // E2E Test Runner (no radio integration)
    // =====================================================
    // Run against a live API started with: pm2 start radioshaq-api --env test
    // Then: pm2 start ecosystem.config.js --only radioshaq-e2e
    {
      name: 'radioshaq-e2e',
      script: require('fs').existsSync(venvPython) ? venvPython : 'python',
      args: [
        '-m', 'pytest',
        'tests/integration',
        '-v',
        '--tb=short',
        '-m', 'integration and live_api',
      ],
      cwd: __dirname,
      instances: 1,
      exec_mode: 'fork',
      autorestart: false,
      watch: false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'test',
        BASE_URL: 'http://127.0.0.1:8001',
        RADIOSHAQ_MODE: 'field',
        RADIOSHAQ_RADIO__ENABLED: 'false',
        RADIOSHAQ_RADIO__AUDIO_INPUT_ENABLED: 'false',
        RADIO_ENABLED: 'false',
        DATABASE_URL: 'postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq_test',
        JWT_SECRET: 'test-secret',
      },
      log_file: './logs/e2e-combined.log',
      out_file: './logs/e2e-out.log',
      error_file: './logs/e2e-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss.SSS Z',
      merge_logs: true,
      kill_timeout: 60000,
    },
  ],

  // =====================================================
  // Deployment Configuration
  // =====================================================
  deploy: {
    // Local development deployment
    development: {
      user: process.env.USER || 'radioshaq',
      host: ['localhost'],
      ref: 'origin/main',
      repo: 'https://github.com/radioshaq/radioshaq.git',
      path: homedir + '/.radioshaq/dev',
      'post-deploy': 'pip install -e . && pm2 start ecosystem.config.js --env development',
      env: {
        NODE_ENV: 'development',
      },
    },
    
    // Test environment
    test: {
      user: process.env.USER || 'radioshaq',
      host: ['localhost'],
      ref: 'origin/main',
      repo: 'https://github.com/radioshaq/radioshaq.git',
      path: homedir + '/.radioshaq/test',
      'post-deploy': 'pip install -e ".[test]" && pm2 start ecosystem.config.js --env test',
      env: {
        NODE_ENV: 'test',
      },
    },
    
    // Production-like local deployment
    production: {
      user: process.env.USER || 'radioshaq',
      host: ['localhost'],
      ref: 'origin/main',
      repo: 'https://github.com/radioshaq/radioshaq.git',
      path: homedir + '/.radioshaq/prod',
      'post-deploy': 'pip install -e ".[dev,test]" && pm2 start ecosystem.config.js --env production',
      'pre-setup': 'apt update && apt install -y postgresql-client nodejs npm',
      env: {
        NODE_ENV: 'production',
      },
    },
  },
};
