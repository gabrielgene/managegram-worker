#!/bin/bash

cat <<EOF
apiVersion: extensions/v1beta2
kind: Deployment
metadata:
  labels:
    app: ${NAME}
  name: ${NAME}
spec:
  replicas: 1
  template:
    metadata:
      labels:
        app: ${NAME}
    spec:
      containers:
        resources:
          requests:
            cpu: "0.1"
      - args:
        - python
        - ${PYTHON_ARG}
        image: gabrielgene/${NAME}:${TAG}
        name: ${NAME}
EOF
