from glob import glob
from dotenv import load_dotenv
from github import Github, Commit, RateLimitExceededException, Repository
import csv
import os
import shutil
import git
import time
import uuid
import pandas as pd
import numpy as np

import requests

def read_csv_file(csv_file_name):
    with open(csv_file_name, newline='') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    return data

def save_data_to_csv(repo_data_lst, csv_file_name = None, columns = ["repo_name", "repo_path", "contain_terra_test", "error"]):
    file_exists = os.path.isfile(csv_file_name)
    with open(csv_file_name, "a", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        for data in repo_data_lst:
            writer.writerow(data)
        f.close()
        
def write_commit_data_to_csv(commit_data, csv_file_name = None):
    new_commit_data = {
        "ssh_url": commit_data["ssh_url"],
        "repo_name": commit_data["repo_name"],
        "commit_date": commit_data["commit_date"],
        "commit_html_url": commit_data["html_url"],
        "parent_commit_html_url": commit_data["parent_commit_html_url"],
        "overall_additions": commit_data["overall_additions"],
        "overall_deletions": commit_data["overall_deletions"],
    }
    new_message_data = {
        "commit_html_url": commit_data["html_url"],
        "message": commit_data["message"],
    }
    
    new_file_changes_data_lst = []
    for file in commit_data["file_changes"]:
        new_file_changes_data = {
            "commit_html_url": commit_data["html_url"],
            "filename": file["filename"],
            "additions": file["additions"],
            "changes": file["changes"],
            "deletions": file["deletions"],
        }
        new_file_changes_data_lst.append(new_file_changes_data)
    
    save_data_to_csv([new_commit_data], csv_file_name, ["ssh_url", "repo_name", "commit_date", "commit_html_url", "parent_commit_html_url", "overall_additions", "overall_deletions"])
    save_data_to_csv(new_file_changes_data_lst, csv_file_name.split(".csv")[0] + "_file_changes.csv", ["commit_html_url", "filename", "additions", "changes", "deletions"])
    save_data_to_csv([new_message_data], csv_file_name.split(".csv")[0] + "_message.csv", ["commit_html_url", "message"])
        
def get_total_page(total_result, page_size):
    total_page = total_result//page_size
    if total_result - (page_size*total_page) > 0:
        total_page += 1
    return total_page

def search_commit(save_result_file_location, g, repo_name):
    get_repo_fail = True
    total_page = 0
    while get_repo_fail:
        try:
            repo = g.get_repo(repo_name)
            commits_total = repo.get_commits()
            total_commits = commits_total.totalCount
            total_page = get_total_page(total_commits, 30)
            get_repo_fail = False
        except Exception as e:
            get_repo_fail = True
            print("Fail to get repo", repo_name, " error: ", e)
            time.sleep(60)
            
    for page in range(total_page):
        is_pass = False
        is_get_commit_fail = False
        num_try = 0
        commits = None
        while is_pass == False:
            try:
                commits = repo.get_commits().get_page(page)
                is_pass = True
            except RateLimitExceededException as rate_limit:
                time.sleep(300)
                num_try += 1
                if num_try >= 3:
                    is_pass = True
                    is_get_commit_fail = True
            except requests.exceptions.ReadTimeout as time_out:
                time.sleep(300)
                num_try += 1
                if num_try >= 3:
                    is_pass = True
                    is_get_commit_fail = True
        if is_get_commit_fail or commits is None:
            save_data_to_csv([{"repo_name": repo_name, "error": "Fail to get commit", "page_number": page}], save_result_file_location + f"/{repo_name}/" + "commit_data_error.csv", columns=["repo_name", "error", "page_number"])
            continue
            
        for commit in commits:
            is_commit_pass = False
            commit_num_try = 0
            while is_commit_pass == False:
                try:
                    if len(commit.parents) != 0:
                        parent_commit_html_url = commit.parents[0].html_url
                    else:
                        parent_commit_html_url = ""
                    commit_data = {
                        "ssh_url": repo.ssh_url,
                        "repo_name":repo.name,
                        "commit_date": commit.commit.author.date,
                        "file_changes": [{"filename":file.filename, "additions":file.additions, "changes":file.changes, "deletions":file.deletions} for file in commit.files],
                        "overall_additions": commit.stats.additions,
                        "overall_deletions": commit.stats.deletions,
                        "html_url": commit.html_url,
                        "parent_commit_html_url": parent_commit_html_url,
                        "message": commit.commit.message,
                    }
                    is_commit_pass = True
                    write_commit_data_to_csv(commit_data, save_result_file_location + "commit_data.csv")
                except Exception as e:
                    time.sleep(300)
                    commit_num_try += 1
                    if commit_num_try >= 3:
                        save_data_to_csv([{"repo_name": repo_name, "error": e, "page_number": page}], save_result_file_location + f"/{repo_name}/" + "commit_data_error.csv", columns=["repo_name", "error", "page_number"])
                        is_commit_pass = True

# copy from jupyter
def process_data(file_location):
    df = pd.read_csv(file_location + 'commit_data.csv')
    file_change_df = pd.read_csv(file_location + 'commit_data_file_changes.csv')
    file_change_df = file_change_df.rename(columns={'file_change_uuid': 'link_uuid'})
    file_change_df = file_change_df.groupby('commit_html_url').agg(lambda x: x.tolist())
    new_df = df.merge(file_change_df, on='commit_html_url', how='left')
    update_test_commit = pd.DataFrame()

    for index, row in new_df.iterrows():
        is_contain_test = False
        if row["filename"] is np.nan:
            continue
        for file in row["filename"]:
            if file.endswith('_test.go'):
                is_contain_test = True
                break
        if is_contain_test:
            update_test_commit = pd.concat([update_test_commit, row.to_frame().T])
    update_test_commit['commit_sha'] = update_test_commit['commit_html_url'].apply(lambda x: x.split('/')[-1])
    update_test_commit['parent_sha'] = update_test_commit['parent_commit_html_url'].apply(lambda x: x.split('/')[-1])
    update_test_commit.to_csv(file_location + 'processed_commit_data_update_test.csv', index=False)

load_dotenv()
repo_url_file_name = os.getenv("REPO_URL_CSV_FILE_NAME")
save_result_file_location = os.getenv("SAVE_RESULT_FILE_LOCATION")
git_token = os.getenv("GITHUB_TOKEN")
repo_csv = read_csv_file(repo_url_file_name)
repo_name_list = [repo["repo_path"].split(":")[-1] for repo in repo_csv]

g = Github(git_token)
for repo_name in repo_name_list:
    search_commit(save_data_to_csv, get_total_page, save_result_file_location, g, repo_name)
    process_data(save_result_file_location + f"/{repo_name}/")