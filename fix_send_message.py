with open('src/main.py', 'r') as f:
    lines = f.readlines()

# Find the start of the send_message block
start_idx = None
for i, line in enumerate(lines):
    if line.strip().startswith('elif action == \"send_message\":'):
        start_idx = i
        break

if start_idx is None:
    print("Could not find send_message block")
    exit(1)

# Find the end of the send_message block: we look for the next line that starts with '            elif' or '            except' or '        except' at the same indentation level as the elif line.
# The elif line is at indentation 12 (from the backup: we saw 12 spaces).
# We'll look for the next line that has indentation <= 12 and is not empty and not a comment? Actually, we want to stop before the outer except which is at indentation 8? Let's check the backup.

# From the backup, the structure is:
#            elif action == \"send_message\":   # indent 12
#                ... (indent 16, 20, etc.)
#                     ... (the inner try-except)
#             except Exception as e:   # indent 8
# So the outer except is at indentation 8, which is less than 12.

# Therefore, we can look for the next line that has indentation <= 12 and is not part of the block.

# We'll start from start_idx+1 and go until we find a line that has indentation <= 12 and that is not empty and not a comment? But note: there are empty lines and comments inside the block.

# We'll instead look for the line that starts with '            except Exception as e:' (the outer except) and that is at indentation 8.

# Let's find the line that starts with '            except Exception as e:' and that is after start_idx.

end_idx = None
for i in range(start_idx+1, len(lines)):
    stripped = lines[i].lstrip()
    if stripped.startswith('except Exception as e:'):
        # Check the indentation: we expect it to be 8 spaces? Let's just check that the indentation is less than the elif line's indentation.
        indent = len(lines[i]) - len(stripped)
        if indent < len(lines[start_idx]) - len(lines[start_idx].lstrip()):
            end_idx = i
            break

if end_idx is None:
    # If we didn't find, we'll set end_idx to the next line that starts with '            elif' (for the next action) at the same level as the send_message elif.
    for i in range(start_idx+1, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith('elif action =='):
            indent = len(lines[i]) - len(stripped)
            if indent <= len(lines[start_idx]) - len(lines[start_idx].lstrip()):
                end_idx = i
                break

if end_idx is None:
    # If still not found, we'll set end_idx to the end of the file (but we don't want to do that)
    end_idx = len(lines)

# Now we have the block from start_idx to end_idx-1.
# We want to replace lines[start_idx:end_idx] with a corrected block.

# Let's define the corrected block.
# We'll base it on the original but fix the indentation.

# We'll write the corrected block as follows:

corrected_block = [
    '            elif action == \"send_message\":\n',
    '                room = data.get(\"room\")\n',
    '                message_content = data.get(\"content\")\n',
    '                # Basic input sanitization to prevent injection attacks\n',
    '                if room and message_content and room.startswith(\"chat_\"):\n',
    '                    # Sanitize message content - remove any potential harmful content\n',
    '                    # Limit message length to prevent DoS\n',
    '                    if len(message_content) > 1000:\n',
    '                        message_content = message_content[:1000] + \"...\"\n',
    '                    # Remove any null bytes or control characters that could cause issues\n',
    '                    message_content = \\'\\'\\'.join(char for char in message_content if ord(char) >= 32 or char in \\'\\n\\r\\t\\'\\'\\')\n',
    '                    try:\n',
    '                        conversation_id = int(room.split(\"_\")[1])\n',
    '                        conv_result = await db.execute(\n',
    '                            select(Conversation).where(Conversation.id == conversation_id)\n',
    '                        )\n',
    '                        conversation = conv_result.scalar_one_or_none()\n',
    '                        if conversation and user.id in [conversation.customer_id, conversation.courier_id]:\n',
    '                            new_message = Message(\n',
    '                                conversation_id=conversation_id,\n',
    '                                sender_id=user.id,\n',
    '                                content=message_content,\n',
    '                                message_type=data.get(\"message_type\", \"text\"),\n',
    '                                invoice_description=data.get(\"invoice_description\"),\n',
    '                                invoice_gift_price=data.get(\"invoice_gift_price\"),\n',
    '                                invoice_service_fee=data.get(\"invoice_service_fee\"),\n',
    '                                invoice_delivery_fee=data.get(\"invoice_delivery_fee\"),\n',
    '                                invoice_total=data.get(\"invoice_total\"),\n',
    '                            )\n',
    '                            db.add(new_message)\n',
    '                            await db.commit()\n',
    '                            await db.refresh(new_message)\n',
    '                            \n',
    '                            await manager.broadcast_to_room({\n',
    '                                \"event\": \"chat_message\",\n',
    '                                \"room\": room,\n',
    '                                \"data\": {\n',
    '                                    \"id\": new_message.id,\n',
    '                                    \"conversation_id\": new_message.conversation_id,\n',
    '                                    \"sender_id\": new_message.sender_id,\n',
    '                                    \"content\": new_message.content,\n',
    '                                    \"message_type\": new_message.message_type,\n',
    '                                    \"sent_at\": new_message.sent_at.isoformat(),\n',
    '                                    \"invoice_description\": new_message.invoice_description,\n',
    '                                    \"invoice_gift_price\": new_message.invoice_gift_price,\n',
    '                                    \"invoice_service_fee\": new_message.invoice_service_fee,\n',
    '                                    \"invoice_delivery_fee\": new_message.invoice_delivery_fee,\n',
    '                                    \"invoice_total\": new_message.invoice_total,\n',
    '                                }\n',
    '                            }, room, user.id)\n',
    '                    except Exception as e:\n',
    '                        # Log error internally without exposing details to users\n',
    '                        import logging\n',
    '                        logging.error(f\"WebSocket error sending chat message: {str(e)}\")\n'
]

# Now, we need to make sure that the indentation of the corrected block matches the surrounding code.
# The elif line should be at the same indentation as the previous elif lines.
# We'll compute the indentation of the line before start_idx (which should be the previous elif or the while line).
# Actually, we can just keep the indentation as we have because we are replacing the block and the surrounding lines are at the same level.

# But note: the corrected block we wrote above assumes that the elif line is indented by 12 spaces (relative to the function body?).
# We'll instead make the corrected block have the same indentation as the original lines we are replacing.

# We'll compute the base indent of the elif line in the original code.
base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())

# Now, we'll adjust the corrected block so that each line has the base_indent plus the relative indentation we intended.

# We'll create a new list for the block to insert.
new_block = []
for line in corrected_block:
    # If the line is empty (just newline), we keep it as is.
    if line.strip() == '':
        new_block.append(line)
    else:
        # Determine the intended relative indentation: we assume the lines in corrected_block are written with the elif line at indent 0? 
        # Actually, we wrote the elif line with no leading spaces? Let's see: the first element is '            elif action == \"send_message\":\n'
        # That already has 12 spaces. So we want to keep that as the base.
        # We'll instead not add any extra base_indent because we already included it.
        # But wait, we want the block to be inserted at the same position, so we want the elif line to have the same indentation as the original elif line.
        # The original elif line had base_indent spaces.
        # Our corrected_block's first line already has 12 spaces. We need to adjust so that it has base_indent spaces.
        # We'll compute the number of spaces we want to remove: we want to set the indentation of the elif line to base_indent.
        # We'll strip the line and then add base_indent spaces.
        stripped_line = line.lstrip()
        if stripped_line == '':
            new_block.append(line)
        else:
            new_line = ' ' * base_indent + stripped_line
            new_block.append(new_line)

# Now, replace the lines.
lines[start_idx:end_idx] = new_block

# Write back the file.
with open('src/main.py', 'w') as f:
    f.writelines(lines)

print("Fixed the send_message block.")