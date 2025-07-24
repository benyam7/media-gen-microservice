# API Examples and Usage Guide

This document provides comprehensive examples of how to use the Media Generation Microservice API.

## Table of Contents

- [Authentication](#authentication)
- [Job Management](#job-management)
- [Media Access](#media-access)
- [Health Monitoring](#health-monitoring)
- [Error Handling](#error-handling)
- [Advanced Usage](#advanced-usage)
- [Integration Examples](#integration-examples)

## Authentication

Currently, the API doesn't require authentication, but in production you might want to add API keys or OAuth.

## Job Management

### Creating a Simple Job

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A beautiful sunset over mountains with vibrant colors",
    "parameters": {
      "width": 1024,
      "height": 1024,
      "num_inference_steps": 4
    }
  }'
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z",
  "status_url": "/api/v1/jobs/status/550e8400-e29b-41d4-a716-446655440000",
  "estimated_completion_time": 300
}
```

### Creating a Job with Webhook

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A futuristic cityscape at night",
    "parameters": {
      "aspect_ratio": "16:9",
      "output_quality": 90,
      "seed": 12345
    },
    "webhook_url": "https://your-app.com/webhooks/media-complete",
    "metadata": {
      "user_id": "user123",
      "session_id": "sess456"
    }
  }'
```

### Checking Job Status

**Request:**
```bash
curl "http://localhost:8000/api/v1/jobs/status/550e8400-e29b-41d4-a716-446655440000"
```

**Response (Pending):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "prompt": "A beautiful sunset over mountains with vibrant colors",
  "parameters": {
    "width": 1024,
    "height": 1024,
    "num_inference_steps": 4
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "started_at": null,
  "completed_at": null,
  "duration_seconds": null,
  "retry_count": 0,
  "error_message": null,
  "media": null,
  "progress": 0.0
}
```

**Response (Completed):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "prompt": "A beautiful sunset over mountains with vibrant colors",
  "parameters": {
    "width": 1024,
    "height": 1024,
    "num_inference_steps": 4
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:32:15Z",
  "started_at": "2024-01-15T10:30:05Z",
  "completed_at": "2024-01-15T10:32:15Z",
  "duration_seconds": 130.5,
  "retry_count": 0,
  "error_message": null,
  "media": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "url": "https://storage.example.com/media/generated.png",
      "type": "image",
      "mime_type": "image/png",
      "file_size_bytes": 2048576,
      "width": 1024,
      "height": 1024
    }
  ],
  "progress": 100.0
}
```

### Listing Jobs

**Request:**
```bash
curl "http://localhost:8000/api/v1/jobs?page=1&per_page=20&status=completed"
```

**Response:**
```json
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "prompt": "A beautiful sunset over mountains",
      "created_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:32:15Z",
      "media": [
        {
          "id": "660e8400-e29b-41d4-a716-446655440000",
          "url": "/api/v1/media/660e8400-e29b-41d4-a716-446655440000",
          "type": "image"
        }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "has_next": false,
  "has_prev": false
}
```

### Cancelling a Job

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000"
```

**Response:**
```
HTTP 204 No Content
```

## Media Access

### Getting Media Information

**Request:**
```bash
curl "http://localhost:8000/api/v1/media/660e8400-e29b-41d4-a716-446655440000/info"
```

**Response:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "type": "image",
  "storage_path": "generated/660e8400-e29b-41d4-a716-446655440000.png",
  "storage_url": "https://storage.example.com/media/generated.png",
  "file_size_bytes": 2048576,
  "mime_type": "image/png",
  "file_extension": ".png",
  "width": 1024,
  "height": 1024,
  "created_at": "2024-01-15T10:32:15Z"
}
```

### Downloading Media File

**Request:**
```bash
curl "http://localhost:8000/api/v1/media/660e8400-e29b-41d4-a716-446655440000" \
  -o downloaded_image.png
```

### Deleting Media

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/media/660e8400-e29b-41d4-a716-446655440000"
```

**Response:**
```
HTTP 204 No Content
```

## Health Monitoring

### Health Check

**Request:**
```bash
curl "http://localhost:8000/api/v1/health"
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "services": {
    "database": true,
    "redis": true
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Kubernetes Probes

**Liveness Probe:**
```bash
curl "http://localhost:8000/api/v1/health/live"
```

**Readiness Probe:**
```bash
curl "http://localhost:8000/api/v1/health/ready"
```

## Error Handling

### Validation Errors

**Request with Invalid Parameters:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "",
    "parameters": {
      "width": -1,
      "height": 5000
    }
  }'
```

**Response:**
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "prompt"],
      "msg": "String should have at least 1 character",
      "input": ""
    },
    {
      "type": "greater_equal",
      "loc": ["body", "parameters", "width"],
      "msg": "Input should be greater than or equal to 128",
      "input": -1
    },
    {
      "type": "less_equal",
      "loc": ["body", "parameters", "height"],
      "msg": "Input should be less than or equal to 2048",
      "input": 5000
    }
  ]
}
```

### Job Not Found

**Response:**
```json
{
  "detail": "Job not found",
  "request_id": "req_123456"
}
```

### Internal Server Error

**Response:**
```json
{
  "error": "Internal server error",
  "message": "An unexpected error occurred",
  "request_id": "req_123456"
}
```

## Advanced Usage

### Model-Specific Parameters

#### Flux Models
```json
{
  "prompt": "A robot in a futuristic lab",
  "parameters": {
    "num_inference_steps": 4,
    "aspect_ratio": "16:9",
    "output_quality": 90,
    "seed": 42
  }
}
```

#### SDXL Models
```json
{
  "prompt": "A detailed portrait of a wise owl",
  "parameters": {
    "width": 1024,
    "height": 1024,
    "num_inference_steps": 50,
    "guidance_scale": 7.5,
    "negative_prompt": "blurry, low quality, distorted",
    "seed": 12345
  }
}
```

### Webhook Payloads

When a job completes, the service sends a POST request to your webhook URL:

**Success Webhook:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "media_url": "https://storage.example.com/media/generated.png",
  "media_id": "660e8400-e29b-41d4-a716-446655440000"
}
```

**Failure Webhook:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error": "Replicate API error: Model not found",
  "error_details": {
    "retry_count": 3,
    "max_retries": 3
  }
}
```

## Integration Examples

### Python Client

```python
import httpx
import asyncio
import time

class MediaGenClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def create_job(self, prompt: str, parameters: dict = None, webhook_url: str = None):
        """Create a new media generation job."""
        data = {"prompt": prompt}
        if parameters:
            data["parameters"] = parameters
        if webhook_url:
            data["webhook_url"] = webhook_url
        
        response = await self.client.post(f"{self.base_url}/api/v1/jobs/generate", json=data)
        response.raise_for_status()
        return response.json()
    
    async def get_job_status(self, job_id: str):
        """Get job status."""
        response = await self.client.get(f"{self.base_url}/api/v1/jobs/status/{job_id}")
        response.raise_for_status()
        return response.json()
    
    async def wait_for_completion(self, job_id: str, timeout: int = 600, poll_interval: int = 5):
        """Wait for job completion."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = await self.get_job_status(job_id)
            if status["status"] in ["completed", "failed", "cancelled"]:
                return status
            await asyncio.sleep(poll_interval)
        raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
    
    async def download_media(self, media_id: str, output_path: str):
        """Download generated media."""
        response = await self.client.get(f"{self.base_url}/api/v1/media/{media_id}")
        response.raise_for_status()
        
        with open(output_path, "wb") as f:
            f.write(response.content)

# Usage example
async def main():
    client = MediaGenClient()
    
    # Create job
    job = await client.create_job(
        prompt="A majestic eagle soaring over mountains",
        parameters={"aspect_ratio": "16:9", "output_quality": 90}
    )
    
    print(f"Created job: {job['id']}")
    
    # Wait for completion
    result = await client.wait_for_completion(job["id"])
    
    if result["status"] == "completed":
        media_id = result["media"][0]["id"]
        await client.download_media(media_id, "generated_eagle.png")
        print("Media downloaded successfully!")
    else:
        print(f"Job failed: {result.get('error_message')}")

if __name__ == "__main__":
    asyncio.run(main())
```

### JavaScript/Node.js Client

```javascript
const axios = require('axios');

class MediaGenClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.client = axios.create({ baseURL: baseUrl });
    }

    async createJob(prompt, parameters = {}, webhookUrl = null) {
        const data = { prompt, parameters };
        if (webhookUrl) data.webhook_url = webhookUrl;

        const response = await this.client.post('/api/v1/jobs/generate', data);
        return response.data;
    }

    async getJobStatus(jobId) {
        const response = await this.client.get(`/api/v1/jobs/status/${jobId}`);
        return response.data;
    }

    async waitForCompletion(jobId, timeout = 600000, pollInterval = 5000) {
        const startTime = Date.now();
        
        while (Date.now() - startTime < timeout) {
            const status = await this.getJobStatus(jobId);
            
            if (['completed', 'failed', 'cancelled'].includes(status.status)) {
                return status;
            }
            
            await new Promise(resolve => setTimeout(resolve, pollInterval));
        }
        
        throw new Error(`Job ${jobId} did not complete within ${timeout}ms`);
    }

    async downloadMedia(mediaId, outputPath) {
        const response = await this.client.get(`/api/v1/media/${mediaId}`, {
            responseType: 'stream'
        });
        
        const fs = require('fs');
        const writer = fs.createWriteStream(outputPath);
        response.data.pipe(writer);
        
        return new Promise((resolve, reject) => {
            writer.on('finish', resolve);
            writer.on('error', reject);
        });
    }
}

// Usage example
async function main() {
    const client = new MediaGenClient();
    
    try {
        // Create job
        const job = await client.createJob(
            "A serene lake with mountains reflected in the water",
            { aspect_ratio: "1:1", output_quality: 85 }
        );
        
        console.log(`Created job: ${job.id}`);
        
        // Wait for completion
        const result = await client.waitForCompletion(job.id);
        
        if (result.status === 'completed') {
            const mediaId = result.media[0].id;
            await client.downloadMedia(mediaId, 'generated_lake.png');
            console.log('Media downloaded successfully!');
        } else {
            console.error(`Job failed: ${result.error_message}`);
        }
    } catch (error) {
        console.error('Error:', error.message);
    }
}

main();
```

### Webhook Handler Example (Express.js)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/webhooks/media-complete', (req, res) => {
    const { job_id, status, media_url, error } = req.body;
    
    console.log(`Job ${job_id} finished with status: ${status}`);
    
    if (status === 'completed') {
        console.log(`Media available at: ${media_url}`);
        // Process the completed media
        processCompletedMedia(job_id, media_url);
    } else if (status === 'failed') {
        console.error(`Job failed with error: ${error}`);
        // Handle the failure
        handleJobFailure(job_id, error);
    }
    
    res.status(200).send('OK');
});

function processCompletedMedia(jobId, mediaUrl) {
    // Your processing logic here
    console.log(`Processing media for job ${jobId}`);
}

function handleJobFailure(jobId, error) {
    // Your error handling logic here
    console.log(`Handling failure for job ${jobId}: ${error}`);
}

app.listen(3000, () => {
    console.log('Webhook server listening on port 3000');
});
```

## Rate Limiting and Best Practices

### Recommended Usage Patterns

1. **Polling Intervals**: Use reasonable polling intervals (5-10 seconds) when checking job status
2. **Timeouts**: Set appropriate timeouts based on your model and image complexity
3. **Error Handling**: Always handle errors gracefully and implement retry logic
4. **Webhooks**: Use webhooks for production applications to avoid polling
5. **Cleanup**: Delete media files when no longer needed to save storage space

### Rate Limits

- Job creation: 10 requests per minute per IP
- Status checks: 60 requests per minute per IP
- Media downloads: No limit (but consider bandwidth)

### Storage Considerations

- Generated media is stored for 30 days by default
- Large images (>2048x2048) may take longer to generate
- Consider using appropriate compression settings for your use case 