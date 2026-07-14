apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.name | default "quantlab" }}-{{ $svc }}
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ $svc }}
spec:
  replicas: {{ index $.Values.replicas $svc | default 2 }}
  selector:
    matchLabels:
      app: {{ $svc }}
  template:
    metadata:
      labels:
        app: {{ $svc }}
    spec:
      containers:
      - name: {{ $svc }}
        image: "{{ $.Values.image.repository }}/{{ $svc }}:{{ $.Values.image.tag }}"
        imagePullPolicy: {{ $.Values.image.pullPolicy }}
        ports:
        - containerPort: {{ index $.Values.ports $svc | default 8000 }}
        resources:
          {{- toYaml (index $.Values.resources $svc | default $.Values.resources.gateway) | nindent 10 }}
        envFrom:
        - configMapRef:
            name: quantlab-config
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $svc }}
  namespace: {{ .Release.Namespace }}
spec:
  selector:
    app: {{ $svc }}
  ports:
  - port: {{ index $.Values.ports $svc | default 8000 }}
    targetPort: {{ index $.Values.ports $svc | default 8000 }}
{{- end }}
