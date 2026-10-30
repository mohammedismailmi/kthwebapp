---
title: Mass Spec AI Calibration
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 🔬 Mass Spectrometer AI Calibration System


An AI-powered virtual calibration platform for Residual Gas Analyzers (RGA), developed at **KTH Royal Institute of Technology**.

## Features

- **Neural Virtual Calibration**: Generate synthetic calibration datasets using a fine-tuned Gemma-2B model
- **Multi-Gas Support**: CH4, O2, N2O, CO2, CO, Ar, N2, H2 at various concentrations
- **Real-time Benchmarking**: Compare AI predictions against physical ground truth from 9,775+ experimental mass spectrometry records
- **Contributor Portal**: Submit your own calibration datasets to improve the model
- **Interactive Dashboard**: Plotly-powered visualization with multi-AMU fingerprint analysis

## Architecture

- **Frontend**: Pure HTML/CSS/JS with Plotly.js charts
- **Backend**: FastAPI (Python)
- **Model**: Gemma-2-2B-it with PEFT LoRA adapter (v9), hosted via HF ZeroGPU Space
- **Database**: SQLite for user auth, predictions tracking, and contributor submissions

## Deployment

Deployed on [Render](https://render.com) via Docker.

## Developed By

Mohammed Ismail M — KTH Royal Institute of Technology
