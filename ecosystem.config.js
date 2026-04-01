module.exports = {
  apps: [
    // Ergo Node - must start first
    {
      name: 'ergo-node',
      script: 'java',
      args: '-jar ergo.jar',
      cwd: '/Users/n1ur0/Documents/git/ergo-testnet',
      watch: false,
      autorestart: true,
      restart_delay: 10000,
      max_memory_restart: '4G',
      env: {
        NODE_ENV: 'production'
      },
      error_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/ergo-node-error.log',
      out_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/ergo-node-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      min_uptime: '10s',
      max_restarts: 10,
      exp_backoff_restart_delay: 100,
      wait_ready: true,
      listen_timeout: 60000,
      kill_timeout: 10000,
      log_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/ergo-node-combined.log',
      merge_logs: true
    },

    // Backend API - depends on ergo-node
    {
      name: 'backend-api',
      script: 'python',
      args: 'api_server.py',
      cwd: '/Users/n1ur0/Documents/git/duckpools-coinflip/backend',
      interpreter: 'python',
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production'
      },
      error_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/backend-api-error.log',
      out_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/backend-api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      min_uptime: '5s',
      max_restarts: 10,
      exp_backoff_restart_delay: 100,
      wait_ready: true,
      listen_timeout: 30000,
      kill_timeout: 5000,
      depends_on: ['ergo-node'],
      log_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/backend-api-combined.log',
      merge_logs: true
    },

    // Off-chain Bot - depends on backend-api
    {
      name: 'off-chain-bot',
      script: 'python',
      args: 'main.py',
      cwd: '/Users/n1ur0/Documents/git/duckpools-coinflip/off-chain-bot',
      interpreter: 'python',
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        NODE_URL: 'http://127.0.0.1:9052',
        BACKEND_URL: 'http://127.0.0.1:8000',
        HEALTH_SERVER_PORT: '8001',
        HEARTBEAT_FILE: '/tmp/off-chain-bot-heartbeat.txt',
        HEARTBEAT_INTERVAL_SECONDS: '30'
      },
      error_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/off-chain-bot-error.log',
      out_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/off-chain-bot-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      min_uptime: '5s',
      max_restarts: 10,
      exp_backoff_restart_delay: 100,
      kill_timeout: 5000,
      depends_on: ['backend-api'],
      log_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/off-chain-bot-combined.log',
      merge_logs: true
    },

    // Frontend Dev - depends on backend-api
    {
      name: 'frontend-dev',
      script: 'npm',
      args: 'run dev',
      cwd: '/Users/n1ur0/Documents/git/duckpools-coinflip/frontend',
      interpreter: 'bash',
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      max_memory_restart: '2G',
      env: {
        NODE_ENV: 'production'
      },
      error_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/frontend-dev-error.log',
      out_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/frontend-dev-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      min_uptime: '5s',
      max_restarts: 10,
      exp_backoff_restart_delay: 100,
      kill_timeout: 5000,
      depends_on: ['backend-api'],
      log_file: '/Users/n1ur0/Documents/git/duckpools-coinflip/logs/frontend-dev-combined.log',
      merge_logs: true
    }
  ]
};
