from kubernetes import client, config
from typing import Dict, Any, Optional, List
import logging

def get_k8s_client():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CustomObjectsApi(), client.CoreV1Api(), client.AppsV1Api(), client.AutoscalingV2Api()

def get_enabled_namespaces(core_api) -> List[str]:
    """Get list of namespaces with auto-hpa enabled"""
    namespaces = core_api.list_namespace()
    enabled_namespaces = []
    for ns in namespaces.items:
        if ns.metadata.annotations and ns.metadata.annotations.get('auto_hpa') == 'true':
            enabled_namespaces.append(ns.metadata.name)
    return enabled_namespaces

def check_for_any_hpa(name: str, namespace: str, autoscaling_api) -> bool:
    """
    Check if any HPA (managed or unmanaged) exists for the given workload
    """
    try:
        hpas = autoscaling_api.list_namespaced_horizontal_pod_autoscaler(namespace)
        for hpa in hpas.items:
            if hpa.spec.scale_target_ref.name == name:
                logging.info(f"Found existing HPA for {name} in namespace {namespace}")
                return True
        return False
    except client.exceptions.ApiException as e:
        logging.error(f"Error checking for HPAs: {str(e)}")
        return False

def get_namespace_config(namespace: str, core_api) -> Optional[Dict]:
    try:
        config_map = core_api.read_namespaced_config_map(
            name="hpa-config",
            namespace=namespace
        )
        return {
            'min_replicas': int(config_map.data.get('min_replicas', '1')),
            'max_replicas': int(config_map.data.get('max_replicas', '10')),
            'cpu_average': int(config_map.data.get('cpu_average', '50')),
            'memory_average': int(config_map.data.get('memory_average', '50'))
        }
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return None
        raise e

def create_hpa_object(name: str, namespace: str, config: Dict, kind: str) -> Dict:
    return {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "managed-by": "auto-hpa-controller"
            }
        },
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": kind,
                "name": name
            },
            "minReplicas": config['min_replicas'],
            "maxReplicas": config['max_replicas'],
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": config['cpu_average']
                        }
                    }
                },
                {
                    "type": "Resource",
                    "resource": {
                        "name": "memory",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": config['memory_average']
                        }
                    }
                }
            ]
        }
    }
