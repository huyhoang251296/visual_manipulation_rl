mkdir -p .ursim/programs
mkdir -p .ursim/urcaps

URCAP_VERSION=1.0.5 # latest version as if writing this
curl -L -o .ursim/urcaps/externalcontrol-${URCAP_VERSION}.jar \
  https://github.com/UniversalRobots/Universal_Robots_ExternalControl_URCap/releases/download/v${URCAP_VERSION}/externalcontrol-${URCAP_VERSION}.jar
