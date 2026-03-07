{{/*
展开 chart 名称。
*/}}
{{- define "texas.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
生成默认的完全限定应用名称。
截断为 63 个字符，因为 Kubernetes 部分名称字段有此长度限制。
如果 release 名称已包含 chart 名称，则直接使用 release 名称。
*/}}
{{- define "texas.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
生成用于 chart 标签的名称和版本。
*/}}
{{- define "texas.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
通用标签
*/}}
{{- define "texas.labels" -}}
helm.sh/chart: {{ include "texas.chart" . }}
{{ include "texas.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
选择器标签
*/}}
{{- define "texas.selectorLabels" -}}
app.kubernetes.io/name: {{ include "texas.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Bot Core 标签
*/}}
{{- define "texas.botCore.labels" -}}
{{ include "texas.labels" . }}
app.kubernetes.io/component: bot-core
{{- end }}

{{/*
Bot Core 选择器标签
*/}}
{{- define "texas.botCore.selectorLabels" -}}
{{ include "texas.selectorLabels" . }}
app.kubernetes.io/component: bot-core
{{- end }}

{{/*
Celery Worker 标签
*/}}
{{- define "texas.celeryWorker.labels" -}}
{{ include "texas.labels" . }}
app.kubernetes.io/component: celery-worker
{{- end }}

{{/*
Celery Worker 选择器标签
*/}}
{{- define "texas.celeryWorker.selectorLabels" -}}
{{ include "texas.selectorLabels" . }}
app.kubernetes.io/component: celery-worker
{{- end }}

{{/*
Celery Beat 标签
*/}}
{{- define "texas.celeryBeat.labels" -}}
{{ include "texas.labels" . }}
app.kubernetes.io/component: celery-beat
{{- end }}

{{/*
Celery Beat 选择器标签
*/}}
{{- define "texas.celeryBeat.selectorLabels" -}}
{{ include "texas.selectorLabels" . }}
app.kubernetes.io/component: celery-beat
{{- end }}

{{/*
Secret 名称 — 如指定了已有 Secret 则使用，否则自动生成
*/}}
{{- define "texas.secretName" -}}
{{- if .Values.existingSecret }}
{{- .Values.existingSecret }}
{{- else }}
{{- include "texas.fullname" . }}
{{- end }}
{{- end }}

{{/*
ConfigMap 名称
*/}}
{{- define "texas.configMapName" -}}
{{- include "texas.fullname" . }}-config
{{- end }}

{{/*
数据库连接 URL — 根据子 chart 自动构建或使用外部配置
*/}}
{{- define "texas.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "postgresql+asyncpg://%s:%s@%s-postgresql:5432/%s" .Values.postgresql.auth.username "$(POSTGRES_PASSWORD)" (include "texas.fullname" .) .Values.postgresql.auth.database }}
{{- else }}
{{- printf "$(DATABASE_URL)" }}
{{- end }}
{{- end }}

{{/*
Redis Broker 连接 URL
*/}}
{{- define "texas.celeryBrokerUrl" -}}
{{- if (index .Values "redis-broker" "enabled") }}
{{- printf "redis://:%s@%s-redis-broker-master:6379/0" "$(REDIS_BROKER_PASSWORD)" (include "texas.fullname" .) }}
{{- else }}
{{- printf "$(CELERY_BROKER_URL)" }}
{{- end }}
{{- end }}

{{/*
Redis Cache 连接 URL
*/}}
{{- define "texas.cacheRedisUrl" -}}
{{- if (index .Values "redis-cache" "enabled") }}
{{- printf "redis://:%s@%s-redis-cache-master:6379/0" "$(REDIS_CACHE_PASSWORD)" (include "texas.fullname" .) }}
{{- else }}
{{- printf "$(CACHE_REDIS_URL)" }}
{{- end }}
{{- end }}

{{/*
完整镜像地址（含标签）
*/}}
{{- define "texas.image" -}}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

