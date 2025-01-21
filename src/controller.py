import kopf
import logging
import asyncio
from kubernetes import client
from utils import (
    get_k8s_client,
    get_namespace_config,
    create_hpa_object,
    get_enabled_namespaces,
    check_for_any_hpa
)
from config import (
    HPA_CONFIG_MAP_NAME,
    MANAGED_BY_LABEL,
    MANAGED_BY_VALUE,
    AUTO_HPA_ANNOTATION
)
from logging_config import setup_logging

@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    """Initialize operator settings and logging"""
    # Initialize logging first
    setup_logging()
    
    settings.posting.enabled = True
    settings.watching.server_timeout = 270
    
    # Get K8s client
    _, core_api, _, _ = get_k8s_client()
    
    # Get namespaces with auto-hpa enabled
    enabled_namespaces = get_enabled_namespaces(core_api)
    settings.watching.namespaces = enabled_namespaces
    logging.info(f"Watching namespaces: {enabled_namespaces}")

def should_process_namespace(namespace_obj) -> bool:
    """Check if namespace should be processed based on annotation"""
    annotations = namespace_obj.metadata.annotations or {}
    return annotations.get(AUTO_HPA_ANNOTATION) == "true"

def process_existing_workloads(namespace: str, apps_api, autoscaling_api, config: dict):
    """Process all existing deployments and statefulsets in a namespace"""
    logging.info(f"Processing existing workloads in namespace {namespace}")
    
    # Process deployments
    deployments = apps_api.list_namespaced_deployment(namespace)
    for deployment in deployments.items:
        name = deployment.metadata.name
        if not check_for_any_hpa(name, namespace, autoscaling_api):
            logging.info(f"Creating HPA for existing deployment {name}")
            hpa = create_hpa_object(name, namespace, config, "Deployment")
            try:
                autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
                    namespace,
                    hpa
                )
                logging.info(f"Created HPA for deployment {name}")
            except client.exceptions.ApiException as e:
                logging.error(f"Failed to create HPA for deployment {name}: {str(e)}")

    # Process statefulsets
    statefulsets = apps_api.list_namespaced_stateful_set(namespace)
    for statefulset in statefulsets.items:
        name = statefulset.metadata.name
        if not check_for_any_hpa(name, namespace, autoscaling_api):
            logging.info(f"Creating HPA for existing statefulset {name}")
            hpa = create_hpa_object(name, namespace, config, "StatefulSet")
            try:
                autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
                    namespace,
                    hpa
                )
                logging.info(f"Created HPA for statefulset {name}")
            except client.exceptions.ApiException as e:
                logging.error(f"Failed to create HPA for statefulset {name}: {str(e)}")

@kopf.on.event('', 'v1', 'namespaces')
def watch_namespaces(event, name, meta, spec, status, **kwargs):
    """Watch for namespace changes and process workloads when needed"""
    if event['type'] not in ['ADDED', 'MODIFIED']:
        return

    custom_api, core_api, apps_api, autoscaling_api = get_k8s_client()
    
    try:
        namespace_obj = core_api.read_namespace(name)
    except client.exceptions.ApiException:
        return

    if not should_process_namespace(namespace_obj):
        return

    config = get_namespace_config(name, core_api)
    if not config:
        logging.warning(f"No HPA config found for namespace {name}")
        return

    # Process existing workloads whenever namespace is enabled
    process_existing_workloads(name, apps_api, autoscaling_api, config)

    # Update operator's watched namespaces
    enabled_namespaces = get_enabled_namespaces(core_api)
    kopf.daemon.running.touch()

@kopf.on.create('deployments')
@kopf.on.create('statefulsets')
async def on_workload_create(spec, name, namespace, body, **kwargs):
    """
    Handle creation of Deployments and StatefulSets.
    Waits 5 seconds to check for custom HPA before creating default one.
    """
    custom_api, core_api, apps_api, autoscaling_api = get_k8s_client()
    
    try:
        namespace_obj = core_api.read_namespace(namespace)
    except client.exceptions.ApiException as e:
        logging.error(f"Failed to read namespace {namespace}: {str(e)}")
        return

    if not should_process_namespace(namespace_obj):
        return

    config = get_namespace_config(namespace, core_api)
    if not config:
        logging.warning(f"No HPA config found for namespace {namespace}")
        return

    # Wait for 5 seconds to allow any custom HPA to be created
    logging.info(f"Waiting 5 seconds before checking for custom HPA for {name}")
    await asyncio.sleep(5)

    # Check if any HPA (custom or managed) exists
    if check_for_any_hpa(name, namespace, autoscaling_api):
        logging.info(f"Found existing HPA for {name}, skipping default HPA creation")
        return

    # No HPA exists, create our default one
    kind = body['kind']
    hpa = create_hpa_object(name, namespace, config, kind)
    try:
        autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
            namespace,
            hpa
        )
        logging.info(f"Created default HPA for {kind.lower()} {name}")
    except client.exceptions.ApiException as e:
        logging.error(f"Failed to create HPA for {kind.lower()} {name}: {str(e)}")

@kopf.on.update('deployments')
@kopf.on.update('statefulsets')
def on_workload_update(spec, name, namespace, body, **kwargs):
    """Handle update events for Deployments and StatefulSets"""
    custom_api, core_api, apps_api, autoscaling_api = get_k8s_client()

    try:
        namespace_obj = core_api.read_namespace(namespace)
    except client.exceptions.ApiException as e:
        logging.error(f"Failed to read namespace {namespace}: {str(e)}")
        return

    if not should_process_namespace(namespace_obj):
        return

    config = get_namespace_config(namespace, core_api)
    if not config:
        logging.warning(f"No HPA config found for namespace {namespace}")
        return

    # Only create HPA if no HPA exists (custom or managed)
    if not check_for_any_hpa(name, namespace, autoscaling_api):
        kind = body['kind']
        hpa = create_hpa_object(name, namespace, config, kind)
        try:
            autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
                namespace,
                hpa
            )
            logging.info(f"Created HPA for updated {kind.lower()} {name}")
        except client.exceptions.ApiException as e:
            logging.error(f"Failed to create HPA for updated {kind.lower()} {name}: {str(e)}")

@kopf.on.delete('deployments')
@kopf.on.delete('statefulsets')
def on_workload_delete(spec, name, namespace, **kwargs):
    """Handle deletion of Deployments and StatefulSets"""
    custom_api, core_api, apps_api, autoscaling_api = get_k8s_client()
    
    try:
        hpa = autoscaling_api.read_namespaced_horizontal_pod_autoscaler(name, namespace)
        if (hpa.metadata and 
            hpa.metadata.labels and 
            hpa.metadata.labels.get(MANAGED_BY_LABEL) == MANAGED_BY_VALUE):
            autoscaling_api.delete_namespaced_horizontal_pod_autoscaler(name, namespace)
            logging.info(f"Deleted HPA {name}")
    except client.exceptions.ApiException as e:
        if e.status != 404:
            logging.error(f"Error deleting HPA {name}: {str(e)}")
            raise e

@kopf.timer('', 'v1', 'configmaps', interval=300.0)
def on_configmap_timer(spec, name, namespace, **kwargs):
    """Periodically check and update HPAs based on ConfigMap changes"""
    if name != HPA_CONFIG_MAP_NAME:
        return

    custom_api, core_api, apps_api, autoscaling_api = get_k8s_client()
    
    try:
        namespace_obj = core_api.read_namespace(namespace)
        if not should_process_namespace(namespace_obj):
            return
    except client.exceptions.ApiException as e:
        logging.error(f"Failed to read namespace {namespace}: {str(e)}")
        return

    config = get_namespace_config(namespace, core_api)
    if not config:
        return

    try:
        hpas = autoscaling_api.list_namespaced_horizontal_pod_autoscaler(namespace)
        
        for hpa in hpas.items:
            if (hpa.metadata and 
                hpa.metadata.labels and 
                hpa.metadata.labels.get(MANAGED_BY_LABEL) == MANAGED_BY_VALUE):
                
                if not hpa.spec or not hpa.spec.scale_target_ref:
                    logging.warning(f"HPA {hpa.metadata.name} has no target reference")
                    continue
                
                kind = hpa.spec.scale_target_ref.kind
                new_hpa = create_hpa_object(
                    hpa.metadata.name,
                    namespace,
                    config,
                    kind
                )
                
                try:
                    autoscaling_api.replace_namespaced_horizontal_pod_autoscaler(
                        hpa.metadata.name,
                        namespace,
                        new_hpa
                    )
                    logging.info(f"Updated HPA {hpa.metadata.name}")
                except client.exceptions.ApiException as e:
                    logging.error(f"Failed to update HPA {hpa.metadata.name}: {str(e)}")
                    
    except client.exceptions.ApiException as e:
        logging.error(f"Failed to list HPAs in namespace {namespace}: {str(e)}")
