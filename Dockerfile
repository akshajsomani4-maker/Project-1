# Cube.dev semantic layer: metrics-as-code, governed REST API.
FROM cubejs/cube:latest

# Cube loads its config from <cwd>/cube.js — the image workdir is /cube/conf —
# and resolves CUBEJS_SCHEMA_PATH *relative to that cwd*, so keep it relative.
ENV CUBEJS_SCHEMA_PATH=model

COPY cube.js /cube/conf/cube.js
COPY model /cube/conf/model

EXPOSE 4000
