import os
import click
import aiohttp
import asyncio
import requests
from urllib import parse


class SonarSpider:
    def __init__(self, url, path, threads):
        self.path = path
        self.threads = threads
        self.semaphore = asyncio.Semaphore(self.threads)
        if self.request(url):
            self.url = url
            print("connect successfully")
        else:
            exit(0)

    def list_project(self):
        api = "/api/components/search_projects?ps=500"
        headers = {"Accept": "application/json"}
        projects = self.request(parse.urljoin(self.url, api), headers).json()

        for project in projects["components"]:
            print(project["name"])

    def list_project_file(self, project_name, page=1) -> list:
        api = "api/measures/component_tree?ps=500&baseComponentKey=%s&metricKeys=alert_status&p=%d" % (project_name, page)
        json = self.request(parse.urljoin(self.url, api)).json()
        files = []
        if json["paging"]["pageIndex"] * json["paging"]["pageSize"] < json["paging"]["total"]:
            return files + self.list_project_file(project_name, page+1)
        return [file["key"] for file in json["components"]]

    def crawl_project_code(self, project_name):
        if not self.path:
            self.path = project_name
        loop = asyncio.get_event_loop()
        files = self.list_project_file(project_name)
        print("total %d files" % len(files))
        loop.run_until_complete(self.crawl(files))

    async def crawl(self, files):
        tasks = [self.save_code(file) for file in files]
        await asyncio.gather(*tasks)

    async def save_code(self, filename):
        api = "/api/sources/raw?key=%s" % parse.quote(filename)
        file = os.path.split(parse.unquote(filename).split(":")[1])
        async with self.semaphore:
            data = await self.async_request(parse.urljoin(self.url, api))
            if data and file[1]:
                print(filename)
                dir_name = os.path.join(self.path, file[0])
                if not os.path.exists(dir_name):
                    os.makedirs(dir_name)
                with open(os.path.join(dir_name, file[1]), "w", encoding="utf-8") as f:
                    f.write(data)

    def request(self, url, headers=None):
        try:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                return r
        except:
            return None

    async def async_request(self, url):
        async with aiohttp.request("GET", url) as resp:
            if resp.status != 200:
                resp.raise_for_status()
                print(resp.status)
            return await resp.text()


@click.command()
@click.option("--url", "-u")
@click.option("--list", "-l", "is_list", is_flag=True)
@click.option("--project", "-p")
@click.option("--threads", "-t", default=20)
@click.option("-output", "-o")
def main(url, project, output,is_list, threads):
    ss = SonarSpider(url, output, threads)
    if is_list:
        ss.list_project()
    elif project:
        ss.crawl_project_code(project)


if __name__ == '__main__':
    main()
