import re

with open('src/main.py', 'r') as f:
    lines = f.readlines()

# We are going to fix the websocket_endpoint function.
# We know the function starts at line 214 (0-indexed line 213) with '@app.websocket("/ws")'
# and the function definition is at line 215 (0-indexed line 214): 'async def websocket_endpoint(websocket: WebSocket, token: str):'

# We'll find the start and end of the function by looking for the next line that is not indented (or less indented) after the function start.
# But note: the function contains nested blocks.

# Instead, we can process the entire file and when we are inside the function, we adjust the indentation.

# We'll use a simple state machine: we know the function starts at the line with '@app.websocket("/ws")' and ends when we return to the same indentation level as the function definition.

# However, note that there are decorators and the function definition.

# Let's find the line with the function definition.
start_line = None
for i, line in enumerate(lines):
    if line.strip().startswith('async def websocket_endpoint'):
        start_line = i
        break

if start_line is None:
    print("Could not find websocket_endpoint function")
    exit(1)

# The function definition line should be at indent 0? Actually, it's at the module level, so indent 0.
# We'll set the base indent to 0.
base_indent = 0

# Now, we'll process lines from start_line to the end of the file, but we'll stop when we find a line that is not indented more than base_indent and is not empty and not a comment? Actually, we stop when we return to base_indent and the line is not part of the function.

# We'll instead process the entire file and when we are inside the function (from start_line to the end of the function), we will adjust the indentation by adding 4 spaces to every line? Not exactly.

# We know that the function body should be indented by 4 spaces relative to the function definition.

# But note: the function definition line itself is at indent 0, so the body should be at indent 4.

# However, the function definition line includes the parameters and the colon, and then the body starts on the next line.

# We'll set a flag when we are inside the function body.

# We'll consider that we are inside the function body from the line after the function definition until we return to indent 0 (or less) and the line is not empty and not a comment? Actually, we stop when we hit a line that is at indent 0 and is not empty and not a comment and not part of a string? This is complex.

# Given the complexity, let's instead rewrite the function from scratch using the original logic but with correct indentation.

# We'll extract the original function lines (from start_line to the end of the function) and then we will re-indent them.

# How to find the end of the function? We'll look for the first line after start_line that has indent <= base_indent and is not empty and not a comment? But note: the function might have empty lines and comments.

# We'll use a heuristic: we'll look for the first line after start_line that has indent == base_indent and that is not empty and does not start with '#' and is not part of a multi-line string? We'll assume that the function ends when we hit a line that is at the same indentation level as the function definition and is not empty and not a comment.

# However, note that there might be a blank line at the end of the function.

# Let's try to find the end by looking for a line that has indent == base_indent and that is not empty and not a comment and that is not inside a bracket? We'll do a simple version.

# We'll start from start_line+1 and go until we find a line that has indent <= base_indent and that is not empty and not a comment.

end_line = None
for i in range(start_line+1, len(lines)):
    stripped = lines[i].lstrip()
    if stripped == '' or stripped.startswith('#'):
        continue
    indent = len(lines[i]) - len(stripped)
    if indent <= base_indent:
        end_line = i
        break

if end_line is None:
    # If we didn't find, set to the end of the file
    end_line = len(lines)

# Now, we have the function lines from start_line to end_line-1.
function_lines = lines[start_line:end_line]

# The function definition line (at index 0 in function_lines) should be at indent 0.
# We want to re-indent the entire function block so that:
#   - The function definition line remains at indent 0.
#   - The body of the function (everything after the function definition line) is indented by 4 spaces.

# We'll leave the function definition line as is, and then for every line after that, we will add 4 spaces of indentation.

# But note: the function definition line might have a continuation? It doesn't.

# We'll create new lines for the function:
#   [function_lines[0]]  # the def line
#   then for each line in function_lines[1:], we add '    ' (4 spaces) at the beginning.

# However, note that the function definition line might already have some indent? We expect it to be 0.

# Let's check the indent of the function definition line:
func_def_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
if func_def_indent != 0:
    print("Warning: function definition line is not at indent 0, but at", func_def_indent)
    # We'll still treat it as the base.

# We'll set the base indent to the indent of the function definition line.
base_indent = func_def_indent

# Now, we want the body to be indented by base_indent + 4.

new_function_lines = [lines[start_line]]  # keep the function definition line as is
for line in function_lines[1:]:
    # If the line is empty, we keep it empty.
    if line.strip() == '':
        new_function_lines.append(line)
    else:
        # Add 4 spaces to the indentation.
        current_indent = len(line) - len(line.lstrip())
        new_line = ' ' * (current_indent + 4) + line.lstrip()
        new_function_lines.append(new_line)

# Now, replace the old function lines with the new ones.
lines[start_line:end_line] = new_function_lines

# Write back the file.
with open('src/main.py', 'w') as f:
    f.writelines(lines)

print("Fixed the indentation of the websocket_endpoint function.")