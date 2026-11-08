# PostBop

**PostBop** is a lightweight, native Linux desktop application for quickly sending posts, drafts, and ideas into [Buffer](https://buffer.com/) without interrupting your workflow.

Built with GTK4 and libadwaita, PostBop provides a simple way to compose content, attach images or links, select your destinations, and send everything to Buffer in just a few clicks.

The goal is simple:

> **Open. Drop. Done.**

PostBop isn't intended to replace Buffer's full web interface. It's designed to complement it, providing a fast, focused desktop experience for capturing content and getting it into your publishing workflow.

Originally developed for the 2026 Buffer Commit developer contest, PostBop is free and open-source software.

## Why "PostBop"?

The name combines elements of **post**, **Buffer**, and **drop**, with a nod to the musical genre *post-bop*.

Jazz historian Stuart Nicholson once described the musical term this way:

> "The term post-bop is a wonderful catch-all, used not so much to describe what a style of music is, but more what it isn't."

In many ways, the same philosophy describes PostBop.

It doesn't attempt to recreate Buffer's entire publishing platform on your desktop. You won't find precise scheduling, queue management, analytics, or elaborate campaign-planning tools.

Instead, PostBop is a catch-all for the content you want to get into Buffer. A place to quickly capture a thought, prepare a draft, or send a finished post to your queue.

Then it gets out of your way.

That's PostBop.

**Open. Drop. Done.**

## Design Philosophy

PostBop was built around a handful of guiding principles:

- **Fast:** Opening the application, composing content, and sending it to Buffer should require minimal effort.
- **Focused:** Keep the interface small and purposeful. Features that belong in Buffer's full publishing platform can stay there.
- **Native:** Built with GTK4 and libadwaita, PostBop integrates naturally with the GNOME desktop rather than wrapping a website in a desktop window.
- **Recoverable:** Unfinished content is saved locally so an interrupted writing session doesn't mean starting over.
- **Privacy-conscious:** Authentication credentials are stored securely using the system's Secret Service, with no application telemetry or analytics.
- **Open source:** PostBop and its companion service are released under the MIT License, encouraging experimentation, modification, and contributions.

## Features

PostBop provides a quick, convenient way to get content into Buffer directly from your Linux desktop.

### Publishing

- **Queue posts:** Send content directly to the publishing queue of one or more connected Buffer channels.
- **Save drafts:** Create drafts for selected channels to review and finish later in Buffer.
- **Capture ideas:** Send content to Buffer Ideas without needing to select individual publishing channels.
- **Multiple destinations:** Select several connected channels and submit content to them in a single operation.

### Content and Attachments

- **Text composition:** Write posts in a simple, focused editor with channel-specific character-limit guidance.
- **Image attachments:** Attach a single image using the file picker or drag-and-drop. Images are temporarily hosted through the PostBop companion service.
- **Link attachments:** Add links to posts using Buffer's native link attachment functionality on supported social networks.
- **Composer recovery:** Automatically save unfinished content, selected destinations, and attachments so you can pick up where you left off.

### Desktop Integration

- **Native GNOME interface:** Built with GTK4 and libadwaita, with support for the desktop's light and dark appearance.
- **Secure authentication:** Connect to Buffer using browser-based OAuth, with credentials stored through the system's Secret Service.
- **Desktop notifications:** Receive notifications when submissions complete.
- **Keep Open mode:** Choose whether PostBop closes after a successful submission or stays open for additional posts.
- **Single-instance behavior:** Reopening PostBop activates the existing application window rather than starting another instance.

### Reliability

- **Partial-success handling:** Track successful and failed destinations independently when submitting to multiple channels.
- **Retry failed submissions:** Retry unsuccessful destinations without automatically reposting to channels that already succeeded.
- **API rate-limit handling:** Respect Buffer's API limits by detecting rate-limit responses, notifying the user, and displaying a countdown until another submission attempt is permitted.
- **Uncertain-submission protection:** When a network failure leaves a submission's status unknown, PostBop prompts you to verify the result before retrying.
- **Local diagnostics:** Application logs help identify authentication, networking, and submission problems.

PostBop is intentionally focused on creating and submitting content. Advanced scheduling, queue management, post history, and analytics remain available through Buffer's full web interface.

## System Requirements

PostBop is designed primarily for Ubuntu and the GNOME desktop environment.

### Supported Environment

- **Operating system:** Ubuntu 24.04 LTS or newer
- **Desktop environment:** GNOME or another Linux desktop supporting GTK4 and libadwaita
- **Python:** 3.12 or newer
- **Authentication storage:** GNOME Keyring or another compatible Secret Service implementation
- **Internet connection:** Required for Buffer authentication, API communication, and media uploads
- **Buffer account:** An active Buffer account with connected social channels

PostBop has been developed and tested on Ubuntu 24.04 LTS. It has also been successfully installed and used on Debian, although compatibility with other Linux distributions and desktop environments is not guaranteed.

### Software Dependencies

PostBop uses the following system libraries:

- GTK 4 and libadwaita for the native desktop interface
- PyGObject for Python integration with GNOME libraries
- libsecret for secure credential storage
- libnotify for desktop notifications

When installing the Debian package through APT, the required software dependencies are installed automatically.

For users running PostBop directly from source, installation instructions are provided below.

## Installation

PostBop can be installed using a Debian package or run directly from its source code.

For most Ubuntu users, **installing the Debian package is recommended**. Developers and anyone interested in exploring or modifying PostBop can run it from source.

### Option 1: Install the Debian Package (Recommended)

Download the latest `.deb` package from the [PostBop GitHub Releases](https://github.com/brock10t/postbop/releases) page.

Open a terminal in the directory containing the downloaded package and run:

```bash
sudo apt install ./postbop_0.1.0-1_all.deb
```

Replace the filename with the version you downloaded, if different.

APT will automatically install any missing system dependencies.

Once installed, PostBop will appear in your desktop's application menu. You can also launch it from a terminal:

```bash
postbop
```

**Updating PostBop**

To update an existing installation, download the newer `.deb` package and install it using the same command. APT will upgrade the installed application while preserving your locally stored preferences and authentication credentials.

**Uninstalling PostBop**

To remove the application:

```bash
sudo apt remove postbop
```

Uninstalling removes the application and its installed files. User-specific preferences, saved composer content, and credentials stored in the system's Secret Service are not automatically deleted.

### Option 2: Run from Source

PostBop can also be run directly from a cloned Git repository. This is the recommended approach for developers who want to examine, modify, or contribute to the project.

These instructions are intended for Ubuntu 24.04 LTS and newer.

**1. Install the required dependencies**

Open a terminal and run:

```bash
sudo apt update

sudo apt install \
    git \
    python3-venv \
    python3-pip \
    python3-gi \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    gir1.2-secret-1 \
    gir1.2-notify-0.7
```

**2. Clone the repository**

```bash
git clone https://github.com/brock10t/postbop.git
cd postbop
```

**3. Create a Python virtual environment**

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
```

The `--system-site-packages` option allows the virtual environment to use PyGObject and GNOME libraries installed through Ubuntu's package manager.

**4. Install PostBop**

```bash
python -m pip install -e .
```

The `-e` option installs PostBop in editable mode. Changes to the Python source code will be reflected the next time the application starts.

**5. Launch PostBop**

```bash
postbop
```

PostBop should open its main window and allow you to connect your Buffer account.

To exit the virtual environment when you're finished:

```bash
deactivate
```

When returning to development later, reactivate the environment with:

```bash
cd postbop
source .venv/bin/activate
```

### First Launch

When PostBop starts for the first time, you'll need to connect your Buffer account.

1. Click **Connect Buffer**.
2. Your default web browser will open Buffer's authorization page.
3. Sign in to Buffer if necessary and authorize PostBop.
4. Return to PostBop after authorization completes.

Your connected Buffer channels will appear in the application, and you can begin composing posts.

Choose **Drop to Queue**, **Drop to Draft**, or **Drop Idea** depending on where you want your content to go.

PostBop remembers your authorization between sessions, so you shouldn't need to repeat the connection process every time you launch it.

## Companion Service

PostBop uses a lightweight PHP companion service to provide functionality that cannot be handled entirely by the desktop application.

The companion service has two primary responsibilities:

- **OAuth authorization relay:** Facilitates the browser-based Buffer authentication process by receiving authorization callbacks and making the results available to the desktop application.
- **Temporary image hosting:** Provides publicly accessible URLs for images attached to posts, allowing Buffer to retrieve those images when processing submissions.

The official PostBop application uses companion infrastructure operated by [**10T Web Design**](https://10t.co/).

### Image Hosting

When you attach an image to a PostBop submission, the application uploads it to the companion service and provides Buffer with a URL where the image can be retrieved.

Uploaded images are temporarily stored on 10T Web Design's infrastructure and are subject to an automatic retention and cleanup policy.

The companion service is designed to:

- Accept authenticated image uploads.
- Generate publicly accessible image URLs for Buffer.
- Maintain operational metadata for upload management and cleanup.
- Remove hosted images after their retention period expires.

**Important:** Uploaded images are accessible through their public URLs during the retention period. Do not upload images containing confidential or sensitive information.

Once Buffer or a connected social network retrieves an image, any copies retained by those services are governed by their respective policies and are outside PostBop's control.

### Self-Hosting

The companion service is open source and included in the PostBop repository.

Developers may deploy their own instance, although doing so requires a compatible web server, appropriate configuration, and changes to the desktop application's companion-service settings.

The standard PostBop release is configured to use the official companion service.

## Privacy

PostBop is designed to collect as little information as reasonably necessary to provide its functionality.

The desktop application does not include telemetry, advertising trackers, or third-party analytics.

### Authentication and Credentials

PostBop connects to Buffer using OAuth authorization.

Authentication begins in your web browser, and the companion service helps relay the authorization result to the desktop application.

Buffer access and refresh tokens are stored locally using the system's Secret Service, typically provided by GNOME Keyring.

When activating image-hosting access, PostBop sends a Buffer access token to the companion service, which uses it to verify the associated Buffer account through Buffer's API. The companion service issues a separate credential for authenticated media uploads and stores a cryptographic hash of that credential rather than the credential itself.

PostBop does not require users to provide their Buffer account passwords directly to the desktop application.

### Local Data Storage

PostBop stores certain information locally to support normal operation and recovery, including:

- Application preferences and recently selected destinations.
- Unfinished composer content and attachment references.
- Cached images associated with unfinished posts.
- Diagnostic logs for troubleshooting application errors.

This information is stored in user-specific locations on the local computer rather than being synchronized through a separate PostBop account.

### Information Sent to External Services

PostBop communicates with external services as part of its normal operation:

**Buffer:** Receives the content, destinations, and attachment information necessary to create posts, drafts, and ideas.

**PostBop Companion Service:** Processes authentication-related requests and temporarily hosts images submitted through the application.

Text-only posts and native link attachments do not require images to be uploaded to the companion service.

### Image Retention

Images uploaded through the official PostBop companion service are retained for 180 days, allowing Buffer and connected social networks time to retrieve them.

A scheduled daily cleanup process identifies expired uploads and removes their hosted image files. Deletion may occur after the expiration date, depending on the cleanup schedule and successful execution.

The companion service retains limited upload metadata for operational and auditing purposes, including the original filename, media type, file size, file hash, associated upload credential, and relevant timestamps. These records are not automatically deleted when the hosted image expires.

Deleting an image from PostBop's local cache, disconnecting your Buffer account, or uninstalling the application does not automatically remove an image already uploaded to the companion service.

Similarly, removing a hosted image does not remove copies already retrieved or published by Buffer or a connected social network.

### Uninstalling PostBop

Removing the Debian package deletes the installed application files but does not automatically erase user-specific application data.

Locally stored preferences, composer recovery data, cached images, diagnostic logs, and credentials may remain after uninstalling.

Users can remove these separately if they no longer wish to retain them.

## Repository Structure

PostBop is organized into two primary components: the native Python desktop application and a PHP companion service that supports authentication and image hosting.

```text
postbop/
├── src/
│   └── postbop/
│       ├── api/             # Buffer API, OAuth, and companion communication
│       ├── models/          # Application data models
│       ├── services/        # Logging and supporting services
│       ├── storage/         # Credentials, preferences, and composer recovery
│       ├── application.py   # GTK application lifecycle
│       ├── window.py        # Main application window and UI
│       ├── settings.py      # Application settings
│       └── validation.py    # Platform-specific character validation
├── companion/              # PHP OAuth relay and image-hosting service
├── data/                   # Desktop launcher and application icon
├── debian/                 # Debian package configuration
├── pyproject.toml          # Python project metadata and entry point
├── README.md               # Project documentation
└── LICENSE                 # MIT License
```

### Desktop Application

The desktop application is written in Python using GTK4 and libadwaita.

Its code separates the graphical interface from Buffer API communication, local storage, and validation logic. This keeps the application relatively easy to understand, maintain, and extend.

### Companion Service

The PHP companion service operates independently of the desktop application. It handles OAuth authorization callbacks and provides temporary hosting for images submitted through PostBop.

The service can be deployed separately from the desktop application, with deployment-specific configuration kept outside the public source code.

### Debian Packaging

The `debian/` directory contains the configuration needed to build an installable Debian package.

PostBop uses Debian's standard Python packaging tools, allowing the application to use GTK, libadwaita, and other libraries supplied by the operating system rather than bundling them into the package.

## Development

PostBop is developed primarily on Ubuntu 24.04 LTS using Python 3.12, GTK4, and libadwaita.

The project uses a conventional Python package structure, with application dependencies provided primarily through the operating system rather than bundled Python libraries.

Developers can follow the [Run from Source](#option-2-run-from-source) instructions above to configure a local development environment.

### Working with the Source

PostBop uses Python's editable installation mode, allowing changes to the application source code to take effect without reinstalling the package.

After activating the development virtual environment, launch the application with:

```bash
postbop
```

Restart the application after making changes to load the updated code.

The desktop application and companion service are maintained as separate components. Most desktop development can be performed without deploying a local companion service because the standard application configuration uses the official PostBop service.

### Building the Debian Package

PostBop includes Debian packaging configuration in the `debian/` directory.

On Ubuntu 24.04, install the required build tools:

```bash
sudo apt install \
    debhelper \
    dh-python \
    pybuild-plugin-pyproject \
    python3-all \
    python3-setuptools \
    dpkg-dev \
    devscripts
```

From the project's root directory, build the package:

```bash
dpkg-buildpackage -b -us -uc
```

The completed `.deb` package is placed in the parent directory.

The package uses Debian's Python build tools to install the application into the system Python environment and includes the desktop launcher and application icon.

The resulting package can be installed using APT, as described in the Installation section.

### Testing

PostBop has been manually tested on Ubuntu 24.04 LTS and Debian 13.

Testing includes Buffer authentication, Queue and Draft submissions, Ideas, multiple destinations, image and link attachments, composer recovery, character-limit validation, and installation and removal of the Debian package.

The application also includes handling for API rate limits, failed submissions, and uncertain submission results.

Automated test coverage is not yet established. Contributions that improve testing and reliability are welcome.

### Contributing

PostBop is open-source software, and contributions, bug reports, and suggestions are welcome.

If you encounter a problem or have an idea for an improvement, please open an issue in the GitHub repository.

Developers interested in contributing code are encouraged to work from the latest development branch and submit pull requests for review.

When contributing, please avoid committing authentication credentials, API secrets, local application data, or generated build artifacts.

## Relationship to Buffer

PostBop is an independent, open-source application built using the [Buffer API](https://buffer.com/developers).

It was originally developed as an entry in the [**2026 Buffer Commit developer contest**](https://buffer.com/api/commit), but it is not an official Buffer product and is not developed, endorsed, or maintained by Buffer.

PostBop is designed to complement Buffer's existing publishing tools, not replace them.

Buffer and its associated trademarks belong to their respective owners.

## License

PostBop is free and open-source software released under the **MIT License**.

Both the Python desktop application and PHP companion service are made available under this license.

You are welcome to use, modify, distribute, and contribute to the project in accordance with the license terms.

See the [LICENSE](LICENSE) file for details.

## About

PostBop was created by **Brock Rogers**, owner of [10T Web Design](https://10t.co/), an independent web development business based in Ohio.

The project began in October 2026 as an entry in Buffer's Commit developer contest and grew into a practical little desktop utility for simplifying everyday social media publishing.

PostBop reflects an approach to software development that values focused functionality, native desktop integration, and tools that solve everyday problems without unnecessary complexity.

And, of course, a little inspiration from jazz.

**Open. Drop. Done.**
