from glob import glob
import csv
import os
import shutil
import git
import time
import subprocess
import multiprocessing


class MyRepo:

    def __init__(self, repo_url, save_clone_repo_path, repo_name="") -> None:
        self.__repo_url = repo_url
        self.__repo_name = repo_name
        self.__have_terra_test = None
        self.__save_clone_repo_path = save_clone_repo_path

    def clone_repository(self):
        repo_name = '---'.join(self.__repo_url.split('.git')
                               [0].split(':')[1].split('/'))
        print(repo_name)

        try:
            git.Repo(self.__save_clone_repo_path + repo_name)
        except:
            git.Repo.clone_from(
                self.__repo_url, self.__save_clone_repo_path + repo_name, depth=1)
        self.__repo_name = repo_name

    def delete_repository(self):
        if os.path.exists(self.__save_clone_repo_path + self.__repo_name) and self.__repo_name != "":
            shutil.rmtree(self.__save_clone_repo_path +
                          self.__repo_name, ignore_errors=True)

    def get_repo_path(self):
        return self.__save_clone_repo_path + self.__repo_name

    def get_repo_url(self):
        return self.__repo_url

    def get_dict(self):
        if self.__have_terra_test is None:
            self.__have_terra_test = self.check_contains_terra_test()
        return {
            "repo_name": self.__repo_name,
            "repo_path": self.__repo_url,
            "contain_terra_test": self.__have_terra_test,
            "error": False
        }

    def get_repo_name(self):
        return self.__repo_name

    def get_file_location(self, query):
        return glob(self.__save_clone_repo_path + self.__repo_name + query, recursive=True)


def get_directory_from_file_path(paths):
    return [os.path.dirname(path) for path in paths]


def copy_file_to_path(path, file_location):
    shutil.copy(file_location, path)


def run_script(run_script):
    p = subprocess.Popen(run_script)
    p.wait()


def check_dependency_commit(commit_sha):
    start = time.perf_counter()
    repo_name = full_repo_name.split("/")[1]
    run_script(["sh", current_repo_path + "/script_download_repo.sh",
                full_repo_name, commit_sha, current_repo_path + "/clone_repo"])
    repo_path = current_repo_path + "/clone_repo/" + \
        repo_name + "-" + commit_sha
    dir_lst = get_directory_from_file_path(
        glob(repo_path + "/**/go.mod", recursive=True))
    for i in range(len(dir_lst)):
        shutil.copy(current_repo_path + "/script_iac_research.sh",
                    dir_lst[i] + "/script_iac_research.sh")
        run_script(["sh", dir_lst[i] + "/script_iac_research.sh", dir_lst[i],
                    current_repo_path + "/output"])
        print("removing file at", dir_lst[i])
        os.remove(os.path.join(dir_lst[i], "script_iac_research.sh"))
    finish = time.perf_counter()
    print(f'Finished in {round(finish-start, 2)} second(s)')

def check_dependency(git_clone_url):
    start = time.perf_counter()
    repo = MyRepo(
        git_clone_url, current_repo_path + "/clone_repo/")
    repo.clone_repository()
    dir_lst = get_directory_from_file_path(
        repo.get_file_location("/**/go.mod"))
    print(dir_lst)
    for i in range(len(dir_lst)):
        shutil.copy(current_repo_path + "/script_iac_research.sh",
                    dir_lst[i] + "/script_iac_research.sh")
        run_script(["sh", dir_lst[i] + "/script_iac_research.sh", dir_lst[i],
                    current_repo_path + "/output"])
        print("removing file at", dir_lst[i])
        os.remove(os.path.join(dir_lst[i], "script_iac_research.sh"))
    finish = time.perf_counter()
    print(f'Finished in {round(finish-start,2 )} second(s)')

def generate_ast_by_commit(input_file, task_id, total_task):
    commit_lst = []
    input_dict = csv.DictReader(open(input_file))
    input_dict = list(input_dict)
    input_list = [input['commit'] for input in input_dict]
    for i, commit in enumerate(input_list):
        if (i+1)%total_task == task_id:
            commit_lst.append(commit)          
    with multiprocessing.Pool(10) as pool:
        pool.map(check_dependency_commit, commit_lst)

def generate_ast_by_repo(input_file, task_id, total_task):
    input_dict = csv.DictReader(open(input_file))
    repo_url_lst = []
    for i, row in enumerate(input_dict):
        if float(row['commit_per_month']) <= 2 or float(row['repo_age']) <= 1 or (i+1)%total_task != task_id:
            continue
        repo_url_lst.append(row['repo_path'])
    with multiprocessing.Pool(3) as pool:
        pool.map(check_dependency, repo_url_lst)

current_repo_path = os.getenv("CURRENT_REPO_PATH")
# repo name with organization name (for generate ast from commit only)
full_repo_name = os.getenv("FULL_REPO_PATH") 
if __name__ == '__main__':
    task_id = os.getenv("SLURM_ARRAY_TASK_ID")
    total_task = os.getenv("TOTAL_TASK")
    input_file = os.getenv("INPUT_FILE")
    mode = os.getenv("MODE")
    assert task_id != None
    assert total_task != None
    assert input_file != None
    assert current_repo_path != None
    task_id = int(task_id)
    if mode == 'repo':
        generate_ast_by_repo(input_file ,task_id, total_task)
    if mode == 'commit':
        assert full_repo_name != None
        generate_ast_by_commit(input_file, task_id, total_task)
