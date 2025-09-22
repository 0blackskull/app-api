# PostgreSQL and Redis Deployment with EBS Storage

## Prerequisites
1. EKS cluster with EBS CSI driver installed
2. kubectl configured to access your cluster
3. Kustomize installed (for environment-specific deployments)

## Deploy

### Option 1: Using Base Manifests (Default)
Apply the manifests in order:

```bash
# 1. Apply storage (creates Redis PVC)
kubectl apply -f storage.yaml

# 2. Apply PostgreSQL (StatefulSet with volume templates)
kubectl apply -f postgres.yaml

# 3. Apply Redis (Deployment with PVC)
kubectl apply -f redis.yaml

# 4. Apply other components
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
```

### Option 2: Using Kustomize (Recommended)
Use environment-specific configurations with proper base/overlay structure:

```bash
# For Development
kubectl apply -k overlays/dev/

# For Production
kubectl apply -k overlays/prod/
```

## Kustomize Structure

The deployment uses a proper Kustomize structure:

```
deployment/
├── base/                    # Base Kubernetes resources
│   ├── kustomization.yaml
│   ├── api-deployment.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   └── ...
└── overlays/               # Environment-specific overlays
    ├── dev/
    │   ├── kustomization.yaml
    │   └── configmap.yaml  # Dev-specific config patch
    └── prod/
        ├── kustomization.yaml
        └── configmap.yaml  # Prod-specific config patch
```

- **Base**: Contains the common Kubernetes resources
- **Overlays**: Environment-specific patches that modify base resources

## Verify Deployment

```bash
# Check pods
kubectl get pods

# Check persistent volumes
kubectl get pv

# Check persistent volume claims
kubectl get pvc

# Check StatefulSet
kubectl get statefulsets

# Check services
kubectl get svc
```

## Key Configuration

- **PostgreSQL**: Uses StatefulSet with `volumeClaimTemplates` for automatic PVC creation
- **Redis**: Uses Deployment with pre-created PVC from storage.yaml
- **Storage**: EBS CSI driver with `ebs-csi-default-sc` storage class
- **Volumes**: PostgreSQL gets 10Gi, Redis gets 1Gi

## Environment-Specific Configurations

### Development Environment (`overlays/dev/`)
- **DEBUG**: Enabled (`True`)
- **CORS_ORIGINS**: Includes localhost ports for development
- **LOG_LEVEL**: `DEBUG`
- **ENV**: `development`
- **EMAIL_FROM**: `dev@astroyaar.co.in`
- **Replicas**: 1 (for resource optimization)

### Production Environment (`overlays/prod/`)
- **DEBUG**: Disabled (`False`)
- **CORS_ORIGINS**: Production domain only
- **LOG_LEVEL**: `INFO`
- **ENV**: `production`
- **EMAIL_FROM**: `info@astroyaar.co.in`
- **Replicas**: 2 (for high availability)

## Access

- PostgreSQL: `metadata-db:5432` (internal service)
- Redis: `redis-cache:6379` (internal service)

## Default Credentials

- PostgreSQL: username=`postgres`, password=`postgres`, database=`postgres`
- Redis: No authentication (internal only)

> **Note**: Change default passwords before production use! 