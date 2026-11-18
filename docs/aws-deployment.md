# TaxBot — AWS Deployment Guide

Two AWS deployment paths are described here:
1. **App Runner** (simpler, recommended for small/medium load)
2. **ECS Fargate + ALB** (full control, recommended for high availability)

Both use Amazon ECR to store Docker images.

---

## Prerequisites

- AWS CLI v2 installed and configured (`aws configure`)
- Docker installed and running
- An AWS account with permissions to create ECR, App Runner or ECS resources
- Your `INGEST_API_KEY`, `LLM_API_KEY`, and other secrets ready

---

## Step 1 — Push images to Amazon ECR

```bash
# Variables — replace with your values
AWS_REGION=ap-south-1          # Mumbai — closest to Indian users
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
API_REPO=taxbot-api
WEB_REPO=taxbot-web

# Create repositories (one-time)
aws ecr create-repository --repository-name $API_REPO  --region $AWS_REGION
aws ecr create-repository --repository-name $WEB_REPO  --region $AWS_REGION

# Authenticate Docker with ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push backend
docker build -t $API_REPO:latest .
docker tag  $API_REPO:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$API_REPO:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$API_REPO:latest

# Build and push frontend
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://your-app-runner-url.awsapprunner.com \
  -t $WEB_REPO:latest taxmitra-web/
docker tag  $WEB_REPO:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$WEB_REPO:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$WEB_REPO:latest
```

---

## Path A — App Runner (recommended)

App Runner is a fully managed container service. It auto-scales and handles
HTTPS, load balancing, and deployments automatically.

### 2A. Create the backend App Runner service

```bash
aws apprunner create-service \
  --service-name taxbot-api \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "'"$AWS_ACCOUNT_ID"'.dkr.ecr.'"$AWS_REGION"'.amazonaws.com/taxbot-api:latest",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "LLM_PROVIDER":   "openai",
          "LLM_MODEL":      "gpt-4o-mini",
          "ALLOWED_ORIGINS": "*",
          "CHROMA_DB_PATH": "/app/data/chromadb",
          "LOG_LEVEL":      "INFO"
        }
      },
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{"Cpu":"1 vCPU","Memory":"2 GB"}' \
  --health-check-configuration '{
    "Protocol":"HTTP","Path":"/ready","Interval":10,"Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":3
  }' \
  --region $AWS_REGION
```

**Note on persistent storage:** App Runner does not support persistent volumes.
For ChromaDB you have two options:
- Use an **EFS mount** via a custom VPC configuration (see AWS docs).
- Replace ChromaDB with a managed alternative (e.g. Pinecone, Weaviate Cloud).

For the ECS Fargate path (Path B), EFS volumes are supported natively.

### 3A. Set secrets via Parameter Store

```bash
# Store secrets (SecureString)
aws ssm put-parameter --name /taxbot/INGEST_API_KEY \
  --value "your-strong-key" --type SecureString --region $AWS_REGION

aws ssm put-parameter --name /taxbot/LLM_API_KEY \
  --value "sk-..." --type SecureString --region $AWS_REGION

aws ssm put-parameter --name /taxbot/SENTRY_DSN \
  --value "https://..." --type SecureString --region $AWS_REGION
```

Add a task execution IAM role with `ssm:GetParameters` permission, then
reference the parameters as environment variable secrets in your App Runner
service configuration.

---

## Path B — ECS Fargate + ALB (abbreviated)

Use this path if you need persistent EFS volumes for ChromaDB, blue-green
deployments, or multi-AZ high availability.

### Key differences from Path A

1. Create a **VPC** with public + private subnets (or use the default VPC).
2. Create an **EFS file system** and access point mounted at `/app/data/chromadb`.
3. Create an **ECS task definition** (Fargate launch type):
   - Container: `taxbot-api`, image from ECR, port 8000
   - Mount point: EFS volume → `/app/data/chromadb`
   - CPU: 1024 (1 vCPU), Memory: 2048 (2 GB)
   - Environment variables from SSM Parameter Store (via `secrets` block)
   - Log driver: `awslogs` → CloudWatch log group `/taxbot/api`
4. Create an **ECS service** with desired count 1 (or 2 for HA).
5. Create an **Application Load Balancer**:
   - Target group: health check path `/ready`, port 8000
   - HTTPS listener (port 443) → target group
   - HTTP listener (port 80) → redirect to HTTPS
6. Attach an **ACM certificate** (see Step 4 below).

```bash
# Example: register task definition (abbreviated — use the AWS console for first setup)
aws ecs register-task-definition --cli-input-json file://ecs-task-def.json
aws ecs create-service \
  --cluster taxbot \
  --service-name taxbot-api \
  --task-definition taxbot-api:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

---

## Step 4 — Custom domain and HTTPS

### Request an ACM certificate

```bash
aws acm request-certificate \
  --domain-name api.yourdomain.com \
  --validation-method DNS \
  --region $AWS_REGION
```

Add the DNS CNAME record shown in ACM to your domain's DNS, wait for
validation (usually < 5 minutes), then:

- **App Runner**: Go to service → Custom domains → Add domain → attach the certificate.
- **ECS + ALB**: Add the certificate ARN to the HTTPS listener in the ALB console.

### IAM least-privilege ECR pull policy

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:GetAuthorizationToken"
    ],
    "Resource": "*"
  }]
}
```

---

## Step 5 — Update ALLOWED_ORIGINS

After deploying the frontend to its final domain, update the backend's
`ALLOWED_ORIGINS` environment variable to match:

```
ALLOWED_ORIGINS=https://taxmitra.yourdomain.com
```

Then redeploy the backend service.

---

## Step 6 — Update NEXT_PUBLIC_API_URL

Rebuild the frontend image with the correct backend URL:

```bash
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.yourdomain.com \
  -t taxbot-web:latest taxmitra-web/
```

Push the new image to ECR and redeploy.
