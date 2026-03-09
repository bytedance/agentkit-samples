class Colors:
    HEADER = "\033[37m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_agent_reflect(text: str):
    """打印智能体反思"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}[智能体反思]{Colors.ENDC}")
    print(f"{Colors.CYAN}{text}{Colors.ENDC}")


def print_agent_act(texts: list):
    """打印智能体行动"""
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[智能体行动]{Colors.ENDC}")
    for text in texts:
        print(f"{Colors.YELLOW}{text}{Colors.ENDC}")


def print_agent_permission(texts: list):
    """打印智能体权限"""
    print(f"\n{Colors.RED}{Colors.BOLD}[智能体权限]{Colors.ENDC}")
    for text in texts:
        print(f"{Colors.RED}{text}{Colors.ENDC}")


def print_header(text: str):
    """打印标题"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_user_request(texts: list):
    """打印用户请求"""
    print(f"\n{Colors.GREEN}{Colors.BOLD}[User]{Colors.ENDC}")
    for text in texts:
        print(f"{Colors.GREEN}{text}{Colors.ENDC}")


def print_agent_respond(texts: list):
    """打印智能体响应"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}[Agent]{Colors.ENDC}")
    for text in texts:
        print(f"{Colors.BLUE}{text}{Colors.ENDC}")
