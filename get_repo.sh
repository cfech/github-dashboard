#!/bin/zsh

curl -L -H "Accept: application/vnd.github+json" -H "Authorization: Bearer ${GITHUB_TOKEN}" https://api.github.com/user/repos