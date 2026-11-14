# ZERO XKCD Comic Generation Service

FastAPI microservice for generating stick-figure educational comics using the XKCD Artist ONNX model and Pillow compositor on Ubuntu.

## Running on Ubuntu

```bash
chmod +x start.sh
./start.sh
```

Or run in background with `nohup`:

```bash
nohup ./start.sh > ~/comic-service.log 2>&1 &
```

## Endpoints

- `GET /health` — Health check
- `POST /generate` — Generate a comic PNG
- `GET /images/{filename}` — Serve generated PNG

