# Changelog

## 0.1.1 — 2026-10-21

- Fix installation with older setuptools and Apple Python/pip combinations;
  declare both requests and aiohttp dependencies.
- Send login credentials as form fields and require a newly issued auth cookie.
- Sign mutation parameters from both params and data, preserving exact URL
  encoding and matching form values in sync and async clients.
- Implement movie status deletion through POST removeMovieStatus and add
  get_movie, set_movie_status and remove_movie_status helpers.
- Support confirmed statuses done, future and never; reject unsupported values.
- Fix real User/Movie field mappings, numeric fields and nested model decoding.
- Unify HTTP errors, malformed JSON, empty success responses and exception aliases.
- Fix cookie replacement and async cookie rotation across session reopening.
- Reject silently ignored request bodies and conflicting parameters.
- Load get_session.py credentials from environment, an ignored local JSON file
  or an interactive prompt, instead of editing tracked source code.
- Add offline regression tests and an explicitly enabled live audit with cleanup.
