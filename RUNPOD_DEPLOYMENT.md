# RunPod Deployment Guide

## Hardware Specifications
- **GPU**: 1× RTX 4090 (24GB VRAM)
- **RAM**: 35GB
- **CPU**: 6 vCPU
- **Storage**: 80GB total

## Quick Start

### 1. Build Docker Image
```bash
docker build -t vos-tool:runpod .
```

### 2. Push to Docker Hub (or RunPod Registry)
```bash
docker tag vos-tool:runpod yourusername/vos-tool:runpod
docker push yourusername/vos-tool:runpod
```

### 3. Deploy on RunPod

1. Go to RunPod Console
2. Create a new Pod with:
   - **Template**: Custom Docker Image
   - **Image**: `yourusername/vos-tool:runpod`
   - **Container Disk**: 20GB (for models and data)
   - **Volume**: 60GB (persistent storage)
   - **Port**: 8501 (Streamlit default)
   - **Expose HTTP Port**: Yes

### 4. Environment Variables (Optional)
Set in RunPod pod configuration:
- `FORCE_READYMODE=true` (enable ReadyMode automation)
- `DEPLOYMENT_MODE=enterprise` (enterprise mode)
- `PORT=8501` (Streamlit port)

## GPU Optimizations

### Models Configured for GPU:
1. **Whisper (ASR)**: 
   - Uses GPU with FP16 precision
   - Flash Attention 2 enabled
   - Batch processing optimized

2. **LLaMA (Rebuttal Detection)**:
   - 35 GPU layers (full offloading to RTX 4090)
   - 4K context window
   - Optimized batch size

3. **Sentence Transformers**:
   - GPU acceleration enabled
   - Batch size: 32

### Performance Expectations:
- **Whisper Transcription**: ~2-5x faster on GPU vs CPU
- **Batch Processing**: Can handle 8+ files in parallel
- **Memory Usage**: ~15-20GB VRAM under full load

## Monitoring GPU Usage

Once deployed, check GPU usage:
```bash
nvidia-smi
```

Or access the RunPod terminal and run:
```bash
watch -n 1 nvidia-smi
```

## Troubleshooting

### GPU Not Detected
- Check CUDA availability: `python3 -c "import torch; print(torch.cuda.is_available())"`
- Verify NVIDIA drivers: `nvidia-smi`
- Check Docker runtime: Ensure `nvidia` runtime is used

### Out of Memory Errors
- Reduce batch sizes in `runpod_config.py`
- Use smaller Whisper model (small instead of medium)
- Reduce LLaMA context window

### Model Download Issues
- Models are downloaded on first use
- Ensure sufficient disk space (20GB+ recommended)
- Check internet connectivity in container

## Storage Management

### Persistent Data:
- Audit results stored in volume
- User data in `/workspace/data` (mount as volume)

### Model Cache:
- Models cached in `/root/.cache/huggingface/`
- Consider mounting as volume for faster restarts

## Performance Tuning

Edit `runpod_config.py` to adjust:
- Batch sizes
- Worker counts
- Model precision (FP16/FP32)
- GPU memory limits

## Support

For issues, check:
1. Container logs in RunPod console
2. GPU utilization with `nvidia-smi`
3. Application logs in Streamlit interface
