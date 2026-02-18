# SecureFlow AI — Privacy Policy

**Last Updated: February 2026**

## Overview

SecureFlow AI is a browser extension designed to protect your privacy when interacting with Large Language Models (LLMs). This policy explains how we handle your data.

## What Data We Process

- **Prompt text** you type into supported LLM sites (ChatGPT, Claude, Gemini)
- **LLM responses** that contain redacted tokens

## How We Process It

1. Your prompt text is sent to our backend sanitization server
2. Personally Identifiable Information (PII) is detected and replaced with anonymous tokens
3. The sanitized prompt is forwarded to the LLM
4. Redacted tokens in the response are restored before you see it

## What We Store

- **Token maps**: Temporarily stored in memory for session restoration (auto-deleted after 30 minutes)
- **Audit logs** (optional): Stored locally in your browser via Chrome storage
- **Settings**: Stored locally in your browser

## What We Do NOT Do

- We do **not** sell your data
- We do **not** share your data with third parties
- We do **not** store your original prompts on our servers permanently
- We do **not** train any models on your data

## Data Security

- All communication uses HTTPS encryption
- Token maps are stored in server memory only (not persisted to disk)
- API key authentication for backend access

## Your Rights

- You can disable the extension at any time
- You can clear all locally stored data from the Settings page
- You can export your audit log as CSV for your records
- You can self-host the backend for complete data sovereignty

## Contact

For privacy concerns, please open an issue on our GitHub repository.
