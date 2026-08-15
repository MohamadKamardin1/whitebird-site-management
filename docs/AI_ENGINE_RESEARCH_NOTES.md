# White Bird AI Optimization Engine — Integration Research Notes

## DeepSeek API verification

The official DeepSeek API documentation is published at `https://api-docs.deepseek.com/`. Its navigation exposes quick-start, model, rate-limit, error-code, JSON-output, tool-call, and API-reference material. The integration will use only a server-side client, with the API key provided through a deployment environment variable. The implementation will validate provider responses against an application-owned schema before surfacing any recommendation in White Bird.

The provider documentation is a reference for request compatibility and response controls only. White Bird remains responsible for role scope, evidence selection, data minimisation, audit logging, output validation, and ensuring generated recommendations do not modify operational records directly.

## Design boundary

The first release is intended to generate explicit on-demand summaries from authoritative data already available to the authenticated user. It will not poll DeepSeek, transmit raw attachments, invent missing operational data, or issue automated workflow changes.
