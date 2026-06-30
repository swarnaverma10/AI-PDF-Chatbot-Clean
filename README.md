---
title: AI PDF Chatbot
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Unity AI PDF Chatbot powered by FastAPI and OpenRouter.
---

# AI PDF Chatbot

A Unity-based AI PDF Chatbot that answers user questions from a predefined knowledge base PDF using FastAPI, OpenRouter API, and pdfplumber.

## Features

- AI-powered PDF Question Answering
- FastAPI REST API
- OpenRouter LLM Integration
- Automatic Knowledge Base Download
- Unity Frontend
- Docker Deployment
- Hugging Face Spaces Ready

## Tech Stack

- Unity
- FastAPI
- Python
- OpenRouter
- pdfplumber
- Docker
- Hugging Face Spaces

## Deployment

The application is containerized using Docker and deployed on Hugging Face Spaces.

The knowledge base PDF is automatically downloaded during startup using the configured `KNOWLEDGE_BASE_URL`.

## Environment Variables

Required:

- `OPENROUTER_API_KEY`

Optional:

- `OPENROUTER_BASE_URL`
- `OPENROUTER_MODEL`
- `KNOWLEDGE_BASE_URL`

## License

MIT