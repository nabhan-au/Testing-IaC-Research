from glob import glob
from dotenv import load_dotenv
from github import Github, Commit, RateLimitExceededException
import csv
import os
import shutil
import git
import time


def read_csv_file(csv_file_name):
    with open(csv_file_name, newline='') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    return data

def save_data_to_csv(repo_data_lst, csv_file_name = None, columns = []):
    file_exists = os.path.isfile(csv_file_name)
    with open(csv_file_name, "a", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        for data in repo_data_lst:
            writer.writerow(data)
        f.close()
        
def get_oldest_commit_date(commits):
    total_commits = commits.totalCount
    if total_commits%30 == 0:
        total_pages = total_commits//30 - 1
    else:
        total_pages = total_commits//30
    oldest_commit = commits.get_page(total_pages)
    return oldest_commit[0].commit.author.date

def get_latest_commit_date(commits):
    last_commit = commits.get_page(0)
    return last_commit[0].commit.author.date

def count_month_between_date(date1, date2):
    return (date2.year - date1.year) * 12 + (date2.month - date1.month)

load_dotenv()
# csv that contain repo url
input_file = os.getenv("INPUT_FILE")
output_file = os.getenv("OUTPUT_FILE")
git_token = os.getenv("GITHUB_TOKEN")

repo_csv = read_csv_file(input_file)
repo_name_list = [repo["name"].split(":")[-1] for repo in repo_csv if repo['commit_per_month'] >= 2]

g = Github(git_token)
for i in range(len(repo_name_list)):
    is_pass = False
    while not is_pass:
        try:
            repo_name = repo_name_list[i]
            repo = g.get_repo(repo_name)
            create_date = repo.created_at
            commits = repo.get_commits()
            total_commits = commits.totalCount
            oldest_commit_date = get_oldest_commit_date(commits)
            latest_commit_date = get_latest_commit_date(commits)
            if count_month_between_date(oldest_commit_date, latest_commit_date) == 0:
                commit_per_month = total_commits
            else:
                commit_per_month =  total_commits/count_month_between_date(oldest_commit_date, latest_commit_date)
            data_for_save_to_csv = {"repo_name": repo_name, "repo_path": repo_csv[i]["name"], "total_commits": total_commits, "oldest_commit_date": oldest_commit_date, "latest_commit_date": latest_commit_date, "month_between": count_month_between_date(oldest_commit_date, latest_commit_date), "commit_per_month": commit_per_month, "repo_age": count_month_between_date(create_date, latest_commit_date)}
            save_data_to_csv([data_for_save_to_csv], output_file, ["repo_name", "repo_path","total_commits", "oldest_commit_date", "latest_commit_date", "month_between", "commit_per_month", "repo_age"])
            is_pass = True
        except RateLimitExceededException:
            print("RateLimitExceededException")
            time.sleep(60)
        except Exception:
            print("Exception")
            is_pass = True
            pass
