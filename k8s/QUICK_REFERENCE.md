# Kubernetes Quick Reference

Quick reference for common operations with the API Template Kubernetes deployment.

## 🚀 Deployment

```bash
# Create secrets
./k8s/scripts/create-secrets.sh

# Deploy everything
kubectl apply -k k8s/base/

# Deploy to specific namespace
kubectl apply -k k8s/base/ -n my-namespace

# View what will be deployed (dry-run)
kubectl apply -k k8s/base/ --dry-run=client
```

## 🔍 Monitoring

```bash
# Watch all pods
kubectl get pods -n api-template-prod -w

# Get all resources
kubectl get all -n api-template-prod

# Check deployment status
kubectl get deployments -n api-template-prod

# Check job status
kubectl get jobs -n api-template-prod

# Check PVC status
kubectl get pvc -n api-template-prod
```

## 📋 Logs

```bash
# View logs (follow)
kubectl logs -n api-template-prod deployment/app -f
kubectl logs -n api-template-prod deployment/worker -f
kubectl logs -n api-template-prod deployment/postgres -f
kubectl logs -n api-template-prod deployment/redis -f
kubectl logs -n api-template-prod deployment/temporal -f
kubectl logs -n api-template-prod deployment/temporal-web -f

# View job logs
kubectl logs -n api-template-prod job/postgres-verifier
kubectl logs -n api-template-prod job/temporal-schema-setup
kubectl logs -n api-template-prod job/temporal-namespace-init

# View previous logs (crashed pods)
kubectl logs -n api-template-prod deployment/app --previous
```

## 🐛 Debugging

```bash
# Describe pod (see events)
kubectl describe pod -n api-template-prod <pod-name>

# Get pod YAML
kubectl get pod -n api-template-prod <pod-name> -o yaml

# Execute command in pod
kubectl exec -it -n api-template-prod deployment/app -- /bin/bash

# Port forward
kubectl port-forward -n api-template-prod svc/app 8000:8000
kubectl port-forward -n api-template-prod svc/temporal-web 8080:8080
```

## 🔄 Updates

```bash
# Update image
kubectl set image deployment/app app=api-template-app:v1.1.0 -n api-template-prod

# Watch rollout
kubectl rollout status deployment/app -n api-template-prod

# Rollback
kubectl rollout undo deployment/app -n api-template-prod

# View history
kubectl rollout history deployment/app -n api-template-prod
```

## 🔧 Configuration

```bash
# Edit ConfigMap
kubectl edit configmap app-config -n api-template-prod

# View ConfigMap
kubectl get configmap app-config -n api-template-prod -o yaml

# Restart deployment (after config change)
kubectl rollout restart deployment/app -n api-template-prod
```

## 🗑️ Cleanup

```bash
# Delete everything
kubectl delete -k k8s/base/

# Delete specific resource
kubectl delete deployment app -n api-template-prod

# Delete namespace (removes everything)
kubectl delete namespace api-template-prod

# Delete jobs only
kubectl delete jobs --all -n api-template-prod
```

## 🔐 Secrets

```bash
# List secrets
kubectl get secrets -n api-template-prod

# View secret (base64 encoded)
kubectl get secret app-secrets -n api-template-prod -o yaml

# Decode secret
kubectl get secret app-secrets -n api-template-prod -o jsonpath='{.data.session_signing_secret}' | base64 -d

# Delete and recreate secrets
kubectl delete secret postgres-secrets -n api-template-prod
./k8s/scripts/create-secrets.sh
```

## 📊 Scaling

```bash
# Scale application deployment
kubectl scale deployment/app --replicas=3 -n api-template-prod

# Scale worker deployment (for increased throughput)
kubectl scale deployment/worker --replicas=3 -n api-template-prod

# Autoscale application
kubectl autoscale deployment/app --min=2 --max=10 --cpu-percent=80 -n api-template-prod

# Autoscale worker
kubectl autoscale deployment/worker --min=1 --max=5 --cpu-percent=80 -n api-template-prod

# View HPA
kubectl get hpa -n api-template-prod
```

## 💾 Storage

```bash
# List PVCs
kubectl get pvc -n api-template-prod

# Describe PVC
kubectl describe pvc postgres-data -n api-template-prod

# View PV
kubectl get pv
```

## 🌐 Networking

```bash
# List services
kubectl get svc -n api-template-prod

# Test service from within cluster
kubectl run -it --rm debug --image=busybox --restart=Never -- wget -O- http://app.api-template-prod.svc.cluster.local:8000/health

# View endpoints
kubectl get endpoints -n api-template-prod
```

## 🔄 Jobs

```bash
# List jobs
kubectl get jobs -n api-template-prod

# Delete completed jobs
kubectl delete job -n api-template-prod --field-selector status.successful=1

# Re-run job
kubectl delete job temporal-schema-setup -n api-template-prod
kubectl apply -f k8s/base/jobs/temporal-schema-setup.yaml
```

## 📈 Resources

```bash
# View resource usage
kubectl top pods -n api-template-prod
kubectl top nodes

# View resource quotas
kubectl describe quota -n api-template-prod

# View resource limits
kubectl describe limitrange -n api-template-prod
```

## 🧪 Testing

```bash
# Test database connection
kubectl exec -it -n api-template-prod deployment/postgres -- psql -U appuser -d appdb -c "\dt"

# Test Redis
kubectl exec -it -n api-template-prod deployment/redis -- redis-cli ping

# Test Temporal
kubectl exec -it -n api-template-prod deployment/temporal-admin-tools -- tctl --ns default namespace describe

# Test application
kubectl port-forward -n api-template-prod svc/app 8000:8000
curl http://localhost:8000/health
```

## 📝 YAML Operations

```bash
# Validate YAML
kubectl apply -k k8s/base/ --dry-run=server

# View rendered manifests
kubectl kustomize k8s/base/

# Diff before applying
kubectl diff -k k8s/base/
```

## 🔍 Events

```bash
# View all events
kubectl get events -n api-template-prod --sort-by='.lastTimestamp'

# Watch events
kubectl get events -n api-template-prod -w

# Filter events by type
kubectl get events -n api-template-prod --field-selector type=Warning
```

## 🏷️ Labels and Selectors

```bash
# Get pods by label
kubectl get pods -n api-template-prod -l app.kubernetes.io/name=app

# Add label
kubectl label pod <pod-name> environment=production -n api-template-prod

# Remove label
kubectl label pod <pod-name> environment- -n api-template-prod
```

## 💡 Tips

- Use `--dry-run=client` to preview changes
- Use `-o yaml` to see full resource definitions
- Use `-w` to watch resources in real-time
- Use `--previous` to see logs from crashed containers
- Use `kubectl explain` to get resource documentation
- Use tab completion: `source <(kubectl completion bash)`

## 🆘 Emergency

```bash
# Force delete stuck pod
kubectl delete pod <pod-name> -n api-template-prod --force --grace-period=0

# Cordon node (prevent scheduling)
kubectl cordon <node-name>

# Drain node (evict pods)
kubectl drain <node-name> --ignore-daemonsets

# View cluster info
kubectl cluster-info
kubectl get nodes
kubectl describe node <node-name>
```

---

**Tip**: Add these aliases to your `~/.bashrc`:

```bash
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgd='kubectl get deployments'
alias kgs='kubectl get services'
alias kl='kubectl logs'
alias kd='kubectl describe'
alias ke='kubectl exec -it'
alias kpf='kubectl port-forward'
```
