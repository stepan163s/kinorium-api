import re
import os
import sys

def main():
    source_path = "kinorium/client.py"
    target_path = "kinorium/client_async.py"
    
    if not os.path.exists(source_path):
        print(f"Error: {source_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(source_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Class and imports
    content = content.replace("class KinoriumClient:", "class KinoriumClientAsync:")
    content = content.replace(
        "from kinorium.utils.request import Request",
        "from kinorium.utils.request_async import RequestAsync as Request"
    )
    
    # 2. _is_async flag
    content = content.replace("_is_async: bool = False", "_is_async: bool = True")
    
    # 3. Method definitions to async def (excluding __init__, properties or specific sync helpers)
    lines = content.splitlines()
    new_lines = []
    
    for i, line in enumerate(lines):
        match = re.match(r'^    def (?!__)([\w]+)\(', line)
        if match:
            method_name = match.group(1)
            # Check if previous line is @property decoration
            is_property = i > 0 and lines[i-1].strip() == "@property"
            is_sync_helper = method_name in ("sign_websocket",)
            
            if not is_property and not is_sync_helper:
                line = "    async " + line[4:]
        new_lines.append(line)
        
    content = "\n".join(new_lines)

    # 4. Await transport calls
    content = content.replace("self._request.get(", "await self._request.get(")
    content = content.replace("self._request.post(", "await self._request.post(")
    content = content.replace("self._request.delete(", "await self._request.delete(")
    content = content.replace("self.request(", "await self.request(")

    # 5. Add async close() method
    close_method = """
    async def close(self):
        \"\"\"Close the client session.\"\"\"
        await self._request.close()
"""
    content = content.rstrip() + "\n" + close_method

    warning = (
        '# ============================================================\n'
        '# ВНИМАНИЕ: этот файл сгенерирован автоматически.\n'
        '# Источник: kinorium/client.py\n'
        '# Команда:  python generate_async_version.py\n'
        '# ============================================================\n\n'
    )
    content = warning + content

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Successfully generated {target_path} from {source_path}")

if __name__ == "__main__":
    main()
