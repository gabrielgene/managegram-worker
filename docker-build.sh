docker build -t gabrielgene/python-worker .
docker tag gabrielgene/python-worker gabrielgene/python-worker:$(git rev-parse HEAD)
