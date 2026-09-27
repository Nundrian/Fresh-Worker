# Security

Fresh Worker runs inside agent environments that can have significant access to your machine and model providers.

## Trust boundary

### Pi

The Pi extension creates another Pi session using the parent's active model/provider. The worker receives only the supplied prompt and has tools disabled, but the prompt still goes to whatever model provider the parent model normally uses.

### Open WebUI

The Open WebUI implementation is a Workspace Tool. Workspace Tools execute Python code on the Open WebUI server.

The tool also requires an Open WebUI API key and makes authenticated HTTP requests to the configured `base_url`.

## Recommendations

- Review the source before installing it.
- Do not paste secrets into worker prompts unless the configured model/provider is allowed to receive them.
- Keep Open WebUI API keys out of source code and configure them through Valves.
- Restrict who may edit/import Workspace Tools.
- Configure `base_url` only to an Open WebUI instance you trust.
- Treat evidence JSON as potentially sensitive because it can contain full worker prompts and responses.
- Keep Fresh Worker child tools disabled unless you intentionally fork the project for a different threat model.

## Reporting a vulnerability

Please open a GitHub issue for non-sensitive security concerns.

For vulnerabilities that would expose secrets or enable exploitation, avoid publishing working exploit details until a private reporting channel is available. You can initially open an issue containing only enough information to request a private contact route.
