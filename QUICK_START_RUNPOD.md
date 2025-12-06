# Quick Start: RunPod Deployment

## 🚀 One-Command Build & Deploy

```bash
# Build optimized image
docker build -f runpod.dockerfile -t vos-tool:runpod .

# Tag and push
docker tag vos-tool:runpod YOUR_DOCKERHUB_USER/vos-tool:runpod
docker push YOUR_DOCKERHUB_USER/vos-tool:runpod
```

## 📦 RunPod Pod Configuration

**Image**: `YOUR_DOCKERHUB_USER/vos-tool:runpod`

**Hardware**:
- GPU: RTX 4090 (24GB)
- RAM: 35GB
- CPU: 6 vCPU
- Storage: 80GB (20GB container + 60GB volume)

**Ports**: 8501 (HTTP)

**Environment Variables** (optional):
```
FORCE_READYMODE=true
DEPLOYMENT_MODE=enterprise
PORT=8501
```

## ✅ Verification

Once deployed, check GPU:
```bash
# In RunPod terminal
nvidia-smi
python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

## 🎯 What's Optimized

- ✅ Whisper: GPU + FP16 + Flash Attention
- ✅ LLaMA: 35 GPU layers + 4K context
- ✅ Sentence Transformers: GPU acceleration
- ✅ Batch Processing: 6 workers + GPU batching

## 📈 Expected Performance

- **Transcription**: 2-5x faster
- **Batch Processing**: 3-4x faster  
- **Memory**: ~15-20GB VRAM peak

## 🔗 Full Documentation

See `RUNPOD_DEPLOYMENT.md` for complete guide.
