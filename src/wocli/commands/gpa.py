"""wocli gpa - 加权GPA计算器，带毒舌点评."""


def grade_to_point(grade):
    """百分制转绩点（4.0制）."""
    if grade >= 90:
        return 4.0
    elif grade >= 85:
        return 3.7
    elif grade >= 82:
        return 3.3
    elif grade >= 78:
        return 3.0
    elif grade >= 75:
        return 2.7
    elif grade >= 72:
        return 2.3
    elif grade >= 68:
        return 2.0
    elif grade >= 64:
        return 1.5
    elif grade >= 60:
        return 1.0
    else:
        return 0.0


def comment(gpa):
    """根据GPA给出毒舌点评."""
    if gpa >= 3.8:
        return "你住在图书馆里。图书馆现在是你家。"
    elif gpa >= 3.5:
        return "再熬一点。提高一分干掉千人。"
    elif gpa >= 3.0:
        return "3分万岁。不难看就行。"
    elif gpa >= 2.5:
        return "正在卷GPA，亿万大学生必须加把劲。"
    elif gpa >= 2.0:
        return "两分够用了。Passing is passing。"
    elif gpa >= 1.0:
        return "至少老师记住你了，怎么记住的你别管。"
    else:
        return "回家吧孩子回家吧，你比较适合做一头猪。"


def run():
    """运行 gpa 命令."""
    print()
    print("  [ GPA 计算器 ]")
    print("  " + "-" * 40)

    try:
        n = int(input("  课程数量: "))
    except (ValueError, EOFError):
        print("\n  输入无效。\n")
        return

    total_points = 0
    total_credits = 0

    for i in range(1, n + 1):
        try:
            credit = float(input(f"  课程{i} - 学分: "))
            grade = float(input(f"  课程{i} - 成绩(0-100): "))
        except (ValueError, EOFError):
            print("\n  输入无效。\n")
            return

        point = grade_to_point(grade)
        total_points += point * credit
        total_credits += credit

    if total_credits == 0:
        print("\n  总学分不能为零。\n")
        return

    gpa = total_points / total_credits

    print()
    print(f"  加权 GPA：{gpa:.2f} / 4.0")
    print(f"  总学分：{total_credits:.0f}")
    print()
    print(f"  {comment(gpa)}")
    print()