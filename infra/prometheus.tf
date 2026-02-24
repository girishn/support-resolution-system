# Prometheus + Grafana stack for scraping agent metrics (and cluster-wide monitoring).
# Uses PodMonitor (recommended) to scrape the triage agent; annotation-based config kept as fallback.

resource "helm_release" "prometheus_stack" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = var.prometheus_stack_chart_version
  namespace  = "monitoring"

  create_namespace = true

  values = [
    yamlencode({
      prometheus = {
        prometheusSpec = {
          # Scrape pods with prometheus.io/scrape (fallback for any annotated pods)
          additionalScrapeConfigs = [
            {
              job_name = "pod-annotations"
              kubernetes_sd_configs = [
                { role = "pod" }
              ]
              relabel_configs = [
                {
                  source_labels = ["__meta_kubernetes_pod_annotation_prometheus_io_scrape"]
                  action        = "keep"
                  regex         = "true"
                },
                {
                  source_labels = ["__meta_kubernetes_pod_annotation_prometheus_io_path"]
                  action        = "replace"
                  target_label  = "__metrics_path__"
                  regex         = "(.+)"
                },
                {
                  source_labels = ["__address__", "__meta_kubernetes_pod_annotation_prometheus_io_port"]
                  action        = "replace"
                  regex         = "([^:]+)(?::\\d+)?;(\\d+)"
                  replacement   = "$$1:$$2"
                  target_label  = "__address__"
                },
                {
                  source_labels = ["__meta_kubernetes_namespace"]
                  action        = "replace"
                  target_label  = "kubernetes_namespace"
                },
                {
                  source_labels = ["__meta_kubernetes_pod_name"]
                  action        = "replace"
                  target_label  = "kubernetes_pod_name"
                }
              ]
            }
          ]
        }
      }
    })
  ]
}

# PodMonitor for triage agent (Prometheus Operator native; more reliable than annotation-based)
resource "kubernetes_manifest" "triage_pod_monitor" {
  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "PodMonitor"
    metadata = {
      name      = "triage-agent"
      namespace = "monitoring"
      labels = {
        "release" = "prometheus"
      }
    }
    spec = {
      selector = {
        matchLabels = {
          app = "triage-agent"
        }
      }
      namespaceSelector = {
        matchNames = ["support-agents"]
      }
      podMetricsEndpoints = [
        {
          port     = "metrics"
          path     = "/metrics"
          interval = "30s"
        }
      ]
    }
  }

  depends_on = [helm_release.prometheus_stack]
}
