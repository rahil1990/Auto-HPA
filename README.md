# Kubernetes Auto-HPA Controller

A Kubernetes operator that automatically manages Horizontal Pod Autoscaling (HPA) for Deployments and StatefulSets. This controller intelligently creates and manages HPAs based on namespace configurations, making cluster autoscaling management easier and more consistent.

## Features

- 🚀 Automatic HPA Creation: Automatically creates HPAs for Deployments and StatefulSets
- 🎯 Namespace-Scoped Configuration: Configure HPA settings per namespace
- 🔄 Real-time Updates: Monitors and updates HPAs based on ConfigMap changes
- 🎛️ Custom HPA Support: Respects existing HPAs and won't override custom configurations
- 📊 Resource-based Scaling: Supports both CPU and Memory-based autoscaling
- 🔍 Smart Detection: 5-second grace period to detect custom HPAs before creating default ones
- 📝 Comprehensive Logging: Detailed logging with 12-hour rotation for better debugging
- 🏷️ Managed Resource Tracking: Labels managed HPAs for easy identification

## Prerequisites

- Kubernetes cluster 1.19+
- Python 3.9+
- `kubectl` configured with cluster access
- Cluster admin privileges for operator deployment

## Installation

1. Clone the repository:
```bash
git clone https://github.com/rahil1990/Auto-HPA.git
cd auto-hpa-controller
```

2. Build the Docker image:
```bash
docker build -t auto-hpa-controller:latest .
```

3. Apply the RBAC configuration:
```bash
kubectl apply -f deploy/rbac.yaml
```

4. Deploy the controller:
```bash
kubectl apply -f deploy/deployment.yaml
```

## Configuration

### Enable Auto-HPA for a Namespace

Add the `auto_hpa: "true"` annotation to your namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
  annotations:
    auto_hpa: "true"
```

### Configure HPA Settings

Create a ConfigMap named `hpa-config` in the target namespace:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hpa-config
  namespace: my-namespace
data:
  min_replicas: "2"
  max_replicas: "10"
  cpu_average: "70"
  memory_average: "80"
```

## How It Works

1. **Namespace Monitoring**: The controller watches for namespaces with the `auto_hpa: "true"` annotation.

2. **Workload Detection**: When a Deployment or StatefulSet is created in an enabled namespace:
   - Waits 5 seconds to allow for custom HPA creation
   - Checks for any existing HPAs
   - Creates a default HPA if none exists

3. **Configuration Management**: 
   - Reads HPA settings from the `hpa-config` ConfigMap
   - Applies default values if not specified:
     - min_replicas: 1
     - max_replicas: 10
     - cpu_average: 50%
     - memory_average: 50%

4. **Continuous Updates**: 
   - Monitors ConfigMap changes every 60 seconds
   - Updates managed HPAs to reflect configuration changes
   - Handles workload updates and deletions

## Advantages

1. **Reduced Manual Configuration**:
   - Eliminates need to manually create HPAs
   - Ensures consistent autoscaling across workloads
   - Reduces human error in HPA configuration

2. **Flexible Management**:
   - Namespace-level configuration
   - Support for custom overrides
   - Easy to enable/disable per namespace

3. **Operational Benefits**:
   - Consistent resource utilization
   - Automated scaling management
   - Reduced operational overhead

4. **Enterprise Ready**:
   - Comprehensive logging
   - Error handling and recovery
   - Non-intrusive deployment

5. **Resource Optimization**:
   - Prevents resource wastage
   - Ensures applications scale based on demand
   - Balances cost and performance

## Logging

The controller maintains logs in `/var/log/auto-hpa/controller.log` with:
- 12-hour rotation
- Detailed operation logging
- Error tracking
- Debug information

## Troubleshooting

Common issues and solutions:

1. **HPAs not being created**:
   - Check namespace annotation
   - Verify ConfigMap exists
   - Check controller logs
   - Verify RBAC permissions

2. **Configuration not updating**:
   - Check ConfigMap format
   - Verify controller logs
   - Check for any error messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
