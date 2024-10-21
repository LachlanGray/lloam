import lloam
import subprocess
import re

def backticks(string):
    pattern = r'`(.*?)`'
    return re.findall(pattern, string)

class ShellAgent(lloam.Agent):
    def __init__(self, goal, root_dir):
        self.goal = goal
        self.root_dir = root_dir
        self.allowed_commands = ["ls", "cat", "touch", "echo", "exit"]

        self.thoughts = []
        self.command_history = ""

    def start(self):
        while True:
            action = self.choose_action()
            self.thoughts.append(action.thought)

            cmd = backticks(action.actions)[0]
            print(cmd)

            if cmd == "":
                continue

            if cmd.startswith("exit"):
                return

            observation = self.run(cmd)
            self.command_history += f"\n$ {cmd}\n{observation}"


    @lloam.prompt
    def choose_action(self):
        """
        {self.goal}
        I'm in the directory {self.root_dir}.
        I'm only allowed to use the commands {self.allowed_commands}.
        The `exit` command is for when I finish the task.

        Here's everything I've done so far:
        ```
        {self.command_history}
        ```

        Concisely, what should I do next?
        [thought]

        What's the next command I should run? (Please write just one command in `backticks`)
        [actions]
        """

    def run(self, command):
        command = command.strip().split()

        try:
            if command[0] not in self.allowed_commands:
                return f"Command not allowed: {command[0]}"
        except:
            breakpoint()

        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stdout if result.returncode == 0 else result.stderr

        return output



if __name__ == "__main__":
    import os
    examples_dir = os.path.dirname(os.path.realpath(__file__))

    root_dir = os.path.join(examples_dir, "static_website")

    os.makedirs(root_dir, exist_ok=True)
    os.chdir(root_dir)
    task = "I want to make a static blog website."

    agent = ShellAgent(task, root_dir)
    agent.start()

