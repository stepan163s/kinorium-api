# Kinorium API Notes

This directory documents the Kinorium Android API behavior recovered for Orivo.

No personal cookies, tokens, emails, passwords, or session values should be stored here.

## Files

- `signing.md` - request signing algorithm and test vectors.
- `authentication.md` - email/password and Apple OAuth session exchange.
- `methods.md` - API methods verified so far.
- `orivo-integration.md` - how Orivo currently uses the API.

## Base URL

```text
https://api.kinorium.com/1.0.3/
```

Every API request requires a `key` query parameter. If the key is missing or invalid, the API returns:

```json
{"key": false}
```
