# PostBop

**PostBop** is a small, native Ubuntu desktop utility for quickly sending content into a Buffer social publishing workflow.

The goal is simple:

> **Open. Drop. Done.**

PostBop is not intended to replace Buffer's full web interface. Instead, it is designed as a lightweight desktop entry point for creating posts, drafts, and ideas without interrupting the user's workflow.

The project is being developed for the 2026 Buffer Commit developer contest.

## Why "PostBop"?

The name began as a combination of **post**, **Buffer**, and **drop**, but it also borrows from the musical term *post-bop*.

That fits the project's philosophy surprisingly well: PostBop is intended to be a small catch-all utility for getting content into a social publishing workflow without becoming a full social media management application itself.

## Project Goals

PostBop is being designed around a few core principles:

- **Fast:** launching, composing, and submitting should require as little friction as possible.
- **Small:** the interface should remain compact and focused.
- **Native:** PostBop is built specifically for the Ubuntu/GNOME desktop using GTK 4 and Libadwaita.
- **Recoverable:** unfinished content should survive application restarts and API/network failures.
- **Private:** OAuth credentials remain on the user's system, and the application includes no telemetry.
- **Open source:** the desktop application and its companion service are developed publicly under the MIT License.

## Initial Target

The first release is targeting:

- Ubuntu 24.04 LTS and newer
- Python
- GTK 4
- PyGObject
- Libadwaita
- Buffer OAuth with PKCE
- Buffer's API
- GNOME Keyring / Secret Service
- Debian `.deb` packaging

Other Linux distributions may work in the future, but Ubuntu is the initial supported platform.

## Planned Core Features

The initial release is expected to support:

- Connect to Buffer through browser-based OAuth
- Drop posts into the Buffer queue
- Drop posts as Buffer drafts
- Drop Buffer Ideas
- Remember recently used destinations and actions
- Restore unfinished composer content
- Attach a single image
- Native Ubuntu notifications
- Keyboard shortcuts
- Basic command-line invocation
- Single-instance application behavior
- Local diagnostic logging
- Native light/dark theme support
- Debian package installation

PostBop intentionally does **not** aim to provide post history, analytics, queue management, or other functionality already available through the full Buffer interface.

## Companion Service

Buffer requires media used by API-created posts to be available from a public URL.

PostBop therefore includes a small companion web service used for:

- temporary image hosting
- OAuth callback relay
- automatic media expiration
- upload audit metadata

The companion service is designed to remain narrow in scope and can be self-hosted.

The official PostBop build will use infrastructure operated by **10T Web Design**.

Production credentials, signing secrets, database passwords, and other deployment-specific configuration are not included in this repository.

## Repository Structure

```
postbop/
├── src/postbop/       # Python GTK desktop application
├── data/              # Desktop files, icons, schemas, and UI resources
├── companion/         # PHP companion service
├── packaging/         # Debian packaging
├── tests/             # Automated tests
├── docs/              # Architecture and project documentation
├── po/                # Future localization resources
└── scripts/           # Development/build utilities
```

## Project Status

PostBop is currently in early development.

The initial project architecture and feature scope have been defined, with implementation beginning during the Buffer Commit development window starting October 28, 2026.

Expect the structure, APIs, and documentation to evolve while the first release is being built.

## Privacy

PostBop is being designed without telemetry or third-party analytics.

OAuth access and refresh tokens are intended to remain on the user's machine and be stored through GNOME Keyring / Secret Service.

Images attached to posts may be temporarily uploaded to the PostBop companion service so Buffer can access them for publishing. Temporary media will be subject to automatic retention and deletion policies.

More detailed privacy documentation will be added as development progresses.

## Relationship to Buffer

PostBop is an independent open-source application that integrates with the Buffer API.

It is not an official Buffer product and is not developed or maintained by Buffer.

Buffer is a trademark of its respective owner.

## License

PostBop is released under the **MIT License**.

See [LICENSE](LICENSE) for details.

## Development

Development instructions will be added as the application structure becomes established.

The initial development and test environment is Ubuntu 24.04 LTS with Python, GTK 4, PyGObject, and Libadwaita.

## About

PostBop is an open-source project written by **Brock Rogers** owner of **10T Web Design**.
