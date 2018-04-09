#!/bin/bash

IMAGE=python-worker NAME=dm-worker PYTHON_ARG=dm_worker.py TAG=$(git rev-parse HEAD) ./k8s/template.sh | kubectl apply -f -
IMAGE=python-worker NAME=task-worker PYTHON_ARG=task_worker.py TAG=$(git rev-parse HEAD) ./k8s/template.sh | kubectl apply -f -
