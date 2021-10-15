# Echo Agent

The echo agent is a containerized static agent. This can be useful in a number
of scenarios, such as full agent testing and development.

## Running the Echo Agent

```sh
$ docker run --rm -it -p 3000:80 dbluhm/echo-agent:latest
```

## Interacting with the Echo Agent

After starting up the agent, you can use `http://localhost:3000/docs` to
interact with the agent through an OpenAPI UI. A client may be generated from
the `openapi.json` also provided at `http://localhost:3000/docs/openapi.json`.

A native python client is included in this project.

### Python Client

```python

from echo_agent import EchoClient, ConnectionInfo, Message

async def main():
	async with EchoClient(base_url="http://localhost:3000") as echo:
		conn: ConnectionInfo = await echo.new_connection(
			seed="00000000000000000000000000000000",
			their_vk="<some verkey value>",
			endpoint="http://example.com"
		)
		await echo.send_message(conn, Message.parse_from_obj({
			"@type": "http://example.org/protocol/1.0/message",
			"value": "example"
		}))
		response = await echo.wait_for_message(conn)
		assert response
```
