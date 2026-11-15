# Render demo deployment

Prepared on codex/scripted-coach. Commit and push the reviewed application and deployment changes before deploying.

1. Render: New > Web Service > connect Vurikk/Junction2026.
2. Branch: codex/scripted-coach. Runtime: Docker. Root directory: blank. Dockerfile: ./Dockerfile.
3. Instance type: Free. Health check: /api/health. Leave Docker command blank.
4. Environment: COACH_LLM_ENABLED=false. No Verda keys needed.
5. Add secret file sbank-demo-data.b64. Paste the contents of the locally generated file with this name.
   Do not commit this file. Render provides it at /etc/secrets/sbank-demo-data.b64.
6. Deploy. Open the supplied HTTPS URL and test both profiles, goal creation, graph and Coach.

To regenerate the secret bundle from the original synthetic dataset:

    python -m backend.package_demo PATH_TO_DATA sbank-demo-data.b64

The bundle contains only CUST04457 and CUST00001 and their linked records. It is base64-encoded ZIP data,
not encryption. It stays on the backend and is excluded from Git and the Docker image.
The runtime extracts it to a temporary directory; only frontend/dist is served as static content.

Python calculations and interactive goals remain on the backend. Goals are shared by demo customer across visitors
and reset on restart. Saved plans remain temporary too unless external durable storage is configured.
Free Render instances sleep after inactivity; open the URL before presenting.

Local verification: production frontend build; static homepage/API and source-file isolation checks;
bundle round-trip retained transaction counts and identical automatic calculations for both customers.
Docker is unavailable locally, so the complete container build must be verified in Render.
