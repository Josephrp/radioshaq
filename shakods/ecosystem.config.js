/**
 * PM2 Ecosystem Configuration for SHAKODS
 * 
 * This configuration manages all processes for development, testing,
 * and local debugging of the SHAKODS system.
 * 
 * Usage:
 *   pm2 start ecosystem.config.js                    # Start all apps
 *   pm2 start ecosystem.config.js --only shakods-api # Start specific app
 *   pm2 start ecosystem.config.js --env test         # Start in test mode
 *   pm2 logs                                         # View all logs
 *   pm2 logs shakods-api                             # View specific app logs
 *   pm2 monit                                        # Monitor processes
 */

const path = require('path');
const homedir = require('os').homedir();

// Use project venv Python so PM2 runs the correct interpreter
const venvPython = path.join(__dirname, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin', 'python' + (process.platform === 'win32' ? '.exe' : ''));

module.exports = {
  apps: [
    // =====================================================
    // Main SHAKODS API Server
    // =====================================================
    {
      name: 'shakods-api',
      script: require('fs').existsSync(venvPython) ? venvPython : 'python',
      args: ['-m', 'shakods.api.server'],
      cwd: __dirname,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['shakods/api', 'shakods/config', 'shakods/database'],
      ignore_watch: ['__pycache__', '*.pyc', '.git', 'logs', '.pytest_cache'],
      max_memory_restart: '512M',
      
      // Environment variables
      env: {
        NODE_ENV: 'development',
        SHAKODS_MODE: 'field',
        SHAKODS_LOG_LEVEL: 'DEBUG',
        SHAKODS_API_HOST: '0.0.0.0',
        SHAKODS_API_PORT: '8000',
        API_PORT: '8000',
        DATABASE_URL: `postgresql+asyncpg://shakods:shakods@127.0.0.1:5434/shakods`,
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
        SHAKODS_MODE: 'field',
        SHAKODS_LOG_LEVEL: 'DEBUG',
        SHAKODS_API_HOST: '127.0.0.1',
        SHAKODS_API_PORT: '8001',
        API_PORT: '8001',
        DATABASE_URL: `postgresql+asyncpg://shakods:shakods@127.0.0.1:5434/shakods_test`,
        JWT_SECRET: 'test-secret',
        RADIO_ENABLED: 'false',
        BRIDGE_ENABLED: 'false',
      },
      
      // Production-like local environment
      env_production: {
        NODE_ENV: 'production',
        SHAKODS_MODE: 'hq',
        SHAKODS_LOG_LEVEL: 'INFO',
        SHAKODS_API_HOST: '0.0.0.0',
        SHAKODS_API_PORT: '8000',
        DATABASE_URL: process.env.DATABASE_URL || `postgresql://shakods:shakods@localhost:5432/shakods`,
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
      name: 'shakods-bridge',
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
      name: 'shakods-orchestrator',
      script: 'python -m shakods.orchestrator.worker',
      cwd: __dirname,
      instances: 2,  // Run 2 orchestrator workers in cluster mode
      exec_mode: 'cluster',
      autorestart: true,
      watch: ['shakods/orchestrator', 'shakods/specialized', 'shakods/prompts'],
      ignore_watch: ['__pycache__', '*.pyc', '.git', 'logs'],
      max_memory_restart: '1G',
      
      env: {
        NODE_ENV: 'development',
        WORKER_TYPE: 'orchestrator',
        SHAKODS_LOG_LEVEL: 'DEBUG',
        ORCHESTRATOR_MAX_ITERATIONS: '50',
        ORCHESTRATOR_TIMEOUT_SECONDS: '300',
        DATABASE_URL: `postgresql://shakods:shakods@localhost:5432/shakods`,
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
        REDIS_URL: process.env.REDIS_URL || '',  // For distributed state if needed
      },
      
      env_test: {
        NODE_ENV: 'test',
        WORKER_TYPE: 'orchestrator',
        SHAKODS_LOG_LEVEL: 'WARNING',
        ORCHESTRATOR_MAX_ITERATIONS: '10',
        ORCHESTRATOR_TIMEOUT_SECONDS: '60',
        DATABASE_URL: `postgresql://shakods:shakods@localhost:5432/shakods_test`,
        JWT_SECRET: 'test-secret',
      },
      
      env_production: {
        NODE_ENV: 'production',
        WORKER_TYPE: 'orchestrator',
        SHAKODS_LOG_LEVEL: 'INFO',
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
      name: 'shakods-mq-worker',
      script: 'python -m shakods.mq.worker',
      cwd: __dirname,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: ['shakods/mq', 'shakods/channels'],
      ignore_watch: ['__pycache__', '*.pyc'],
      max_memory_restart: '512M',
      
      env: {
        NODE_ENV: 'development',
        WORKER_TYPE: 'mq',
        SHAKODS_LOG_LEVEL: 'DEBUG',
        DATABASE_URL: `postgresql://shakods:shakods@localhost:5432/shakods`,
        JWT_SECRET: 'dev-secret-do-not-use-in-production',
      },
      
      env_test: {
        NODE_ENV: 'test',
        WORKER_TYPE: 'mq',
        SHAKODS_LOG_LEVEL: 'WARNING',
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
      name: 'shakods-migrate',
      script: 'alembic upgrade head',
      cwd: __dirname,
      instances: 1,
      exec_mode: 'fork',
      autorestart: false,  // One-shot migration
      watch: false,
      
      env: {
        NODE_ENV: 'development',
        ALEMBIC_CONFIG: './alembic.ini',
        DATABASE_URL: `postgresql://shakods:shakods@localhost:5432/shakods`,
      },
      
      env_test: {
        NODE_ENV: 'test',
        DATABASE_URL: `postgresql://shakods:shakods@localhost:5432/shakods_test`,
      },
      
      log_file: './logs/migrate-combined.log',
      out_file: './logs/migrate-out.log',
      error_file: './logs/migrate-error.log',
      
      // Run migrations before starting other services
      wait_ready: true,
      listen_timeout: 30000,
    },
  ],
  
  // =====================================================
  // Deployment Configuration
  // =====================================================
  deploy: {
    // Local development deployment
    development: {
      user: process.env.USER || 'shakods',
      host: ['localhost'],
      ref: 'origin/main',
      repo: 'https://github.com/shakods/shakods.git',
      path: homedir + '/.shakods/dev',
      'post-deploy': 'pip install -e . && pm2 start ecosystem.config.js --env development',
      env: {
        NODE_ENV: 'development',
      },
    },
    
    // Test environment
    test: {
      user: process.env.USER || 'shakods',
      host: ['localhost'],
      ref: 'origin/main',
      repo: 'https://github.com/shakods/shakods.git',
      path: homedir + '/.shakods/test',
      'post-deploy': 'pip install -e ".[test]" && pm2 start ecosystem.config.js --env test',
      env: {
        NODE_ENV: 'test',
      },
    },
    
    // Production-like local deployment
    production: {
      user: process.env.USER || 'shakods',
      host: ['localhost'],
      ref: 'origin/main',
      repo: 'https://github.com/shakods/shakods.git',
      path: homedir + '/.shakods/prod',
      'post-deploy': 'pip install -e ".[dev,test]" && pm2 start ecosystem.config.js --env production',
      'pre-setup': 'apt update && apt install -y postgresql-client nodejs npm',
      env: {
        NODE_ENV: 'production',
      },
    },
  },
};
