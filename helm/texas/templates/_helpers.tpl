{{/*
Expand the name of the chart.
*/}}
{{- define "texas.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
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
Create chart name and version as used by the chart label.
*/}}
{{- define "texas.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
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
Selector labels
*/}}
{{- define "texas.selectorLabels" -}}
app.kubernetes.io/name: {{ include "texas.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Bot selector labels
*/}}
{{- define "texas.bot.selectorLabels" -}}
{{ include "texas.selectorLabels" . }}
app.kubernetes.io/component: bot
{{- end }}

{{/*
Worker selector labels
*/}}
{{- define "texas.worker.selectorLabels" -}}
{{ include "texas.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Beat selector labels
*/}}
{{- define "texas.beat.selectorLabels" -}}
{{ include "texas.selectorLabels" . }}
app.kubernetes.io/component: beat
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "texas.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "texas.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image tag — defaults to Chart.appVersion
*/}}
{{- define "texas.imageTag" -}}
{{- default .Chart.AppVersion .Values.image.tag }}
{{- end }}

{{/*
Full image reference
*/}}
{{- define "texas.image" -}}
{{- printf "%s:%s" .Values.image.repository (include "texas.imageTag" .) }}
{{- end }}

{{/*
Secret name to use
*/}}
{{- define "texas.secretName" -}}
{{- if .Values.existingSecret }}
{{- .Values.existingSecret }}
{{- else }}
{{- include "texas.fullname" . }}
{{- end }}
{{- end }}

{{/*
ConfigMap name
*/}}
{{- define "texas.configMapName" -}}
{{- include "texas.fullname" . }}
{{- end }}
