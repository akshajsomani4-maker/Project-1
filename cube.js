/**
 * Cube semantic-layer configuration (local development + Docker).
 *
 * Cube >= 1.7 validates this file strictly: `dbType`, `devMode`, `telemetry`
 * and `cacheAndQueueDriver` are no longer allowed here — those knobs come
 * from environment variables (CUBEJS_DB_TYPE, CUBEJS_DEV_MODE, ...), which
 * infra/docker-compose.yml sets. This file only wires the driver + schema.
 */
module.exports = {
  apiSecret: process.env.CUBEJS_API_SECRET || 'metricmind-dev-secret',

  // Postgres is the governed warehouse for the MetricMind semantic layer.
  driverFactory: () => ({
    type: process.env.CUBEJS_DB_TYPE || 'postgres',
    url:
      process.env.CUBEJS_DB_URL ||
      'postgres://metricmind:metricmind@localhost:5432/metricmind',
  }),

  schemaPath: process.env.CUBEJS_SCHEMA_PATH || 'model',
};
