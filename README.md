# Research ACE (Assistant Code Execution) Service

Architecture doc: https://www.notion.so/openai/Assistant-Code-Execution-ACE-Service-Architecture-Proposal-8f2bade778cd43d6bbe090dcc897eb8b

The entry point to the project is `bin/dev.py`. This doc highlights important operations to know about, but is not an exhaustive list. For the rest, call `bin/dev.py` and its subcommands with `--help`.

## Pre Commit Hook

Run `pre-commit install -t pre-push` in the git directory after cloning the repository.

## Local Development

**Note**: This is tested for `kubectl` version 1.22.X. If you run into issues and have a different version, try upgrading/downgrading (easiest way is rerunning `bin/boostrap.sh` in `workstation-config`).

Install kind and docker for desktop: https://kind.sigs.k8s.io/docs/user/quick-start/

Then complete the rest of the setup via:

```
./bin/dev.py local setup
```

**Note**: From this step, if you see the kind cluster successfully created but shows this error: `The connection to the server 127.0.0.1:<port_number> was refused - did you specify the right host or port?`, one potential reason is that the `$DOCKER_HOST` environment variable is override (e.g., if you followed [applied eng onboarding](https://www.notion.so/openai/Applied-Technical-Onboarding-ee31b0e5411e405e8076ae0750bafbc0#3c26ce6cdea34cc2a68378d9838612e9), the DOCKER_HOST is pointing to buildbox). Setting `export DOCKER_HOST=''` to let docker client talk to the default local docker daemon fixes this issue.

There's no stand-alone "build" step exposed by this script, because most of the functionality is tied to the kubernetes api. Here's what you'd do to build and test the project:

```
./bin/dev.py local deploy
./bin/dev.py test
```

## Ad-hoc Testing

For debugging, you can `ace_cli` directly to run code against ACE from the command line. To against a local cluster, you can just run the following command under `ace/lib/`:

```
python -m ace_cli --code "print('hi')" --host localhost
```

(optionally add `--allow_internet`)

Here's how you can run code against a production cluster:

```
python -m ace_cli -c <CREDENTIALS_DIR> --code "print('hi')" --host <HOST>
```

`CREDENTIALS_DIR`` is the path prefix for the `client.crt`` and `client.key`` files you received from last pass.

## Local disk space

Make sure your docker VM has enough disk space assigned to it (Matt's configuration is 312GB to be safe). You may start
seeing AceTooManyRequestsException errors otherwise. Often this can be from unused images, which you can clear with:

     docker image prune
     docker system prune`
