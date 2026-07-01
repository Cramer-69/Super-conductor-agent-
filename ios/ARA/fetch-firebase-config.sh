#!/bin/zsh
set -euo pipefail

project_id="conductor-agent"
app_id="1:396823428450:ios:36efa8ee80e1734ead003b"
destination="Configuration/GoogleService-Info.plist"
response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

token="$(gcloud auth print-access-token)"
curl -fsS \
  -H "Authorization: Bearer ${token}" \
  -H "x-goog-user-project: ${project_id}" \
  "https://firebase.googleapis.com/v1beta1/projects/${project_id}/iosApps/${app_id}/config" \
  -o "$response_file"
unset token

plutil -extract configFileContents raw -o - "$response_file" \
  | base64 -D > "$destination"
chmod 600 "$destination"
plutil -lint "$destination"

echo "Firebase configuration saved to ${destination}"
