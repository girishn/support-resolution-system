# Prometheus + Grafana stack for scraping agent metrics (and cluster-wide monitoring).
# Annotation-based scraping (additionalScrapeConfigs) scrapes pods with prometheus.io/scrape=true
# (including triage, billing, technical, feature agents).

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
