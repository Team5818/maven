#!/usr/bin/env python3
import re
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

import requests
import sys
from bs4 import BeautifulSoup
from packaging import version as versiondata

from blessings import Terminal
from tqdm import tqdm
from io import BytesIO

version_regex = re.compile(r"CTRE Phoenix Framework \(No Installer\) package (.+?) \(\.zip\)")


def extract_version(name):
    return version_regex.search(name).group(1)


def get_latest_version():
    r = requests.get('http://www.ctr-electronics.com/hro.html')
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    # find links w/ fitting names
    package_links = soup.find_all("a", text=version_regex)
    # extract link + version
    link_w_version = [(a.attrs['href'], versiondata.parse(extract_version(a.string))) for a in package_links]
    # sort by version number
    link_w_version.sort(key=lambda x: x[1])
    # return highest version
    return link_w_version[-1]


CTR_BASE = Path('./com/ctre/ctrlib')
CTR_JAVA = CTR_BASE / 'ctrlib-java'
CTR_CPP = CTR_BASE / 'ctrlib-cpp'


def get_current_version():
    versions = [versiondata.parse(d.name) for d in CTR_JAVA.iterdir()]
    versions.sort()
    return versions[-1]


def unpack_zip_entry(zfile, name, to):
    data = zfile.read(name)
    with Path(to).open('wb') as f:
        f.write(data)


def main():
    t = Terminal()
    print(t.yellow('Fetching latest version...'))

    dl_link, version = get_latest_version()

    print(t.blue('Found CTRLib version ') +
          t.bold_blue(str(version)) +
          t.blue(' available at ') +
          t.bold_blue(dl_link))

    current_version = get_current_version()
    if current_version >= version:
        print(t.green('Repository already contains this version. Exiting.'))
        return
    print(t.yellow('Repository does not contain this version.'))
    print(t.yellow('Downloading...'))
    print(t.blue, end='')
    buffer = bytearray()
    with requests.get(dl_link, stream=True) as r:
        with tqdm(desc='CTRLib ' + str(version),
                  unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                  file=sys.stdout) as progress_bar:
            for b in r.iter_content(chunk_size=None):
                progress_bar.update(len(b))
                buffer += b

    print(t.yellow('Unpacking...'))

    buffer_as_file = BytesIO(buffer)
    # pick out file name, then drop `.zip`
    folder_name = urlparse(dl_link).path.split('/')[-1][:-4]
    with ZipFile(buffer_as_file) as zipfile:
        ctr_java_version = CTR_JAVA / str(version)
        ctr_java_version.mkdir(exist_ok=True)

        unpack_zip_entry(zipfile,
                         name=folder_name + '/java/lib/CTRE_Phoenix.jar',
                         to=(ctr_java_version / ('ctrlib-java-' + str(version) + '.jar')))
        unpack_zip_entry(zipfile,
                         name=folder_name + '/java/lib/CTRE_Phoenix-sources.jar',
                         to=(ctr_java_version / ('ctrlib-java-' + str(version) + '-sources.jar')))

        so_file = zipfile.read(folder_name + '/java/lib/libCTRE_PhoenixCCI.so')
        ctr_cpp_version = CTR_CPP / str(version)
        ctr_cpp_version.mkdir(exist_ok=True)
        zip_filename = (ctr_cpp_version / ('ctrlib-cpp-' + str(version) + '-linuxathena.zip'))
        with ZipFile(zip_filename, mode='w') as cppzip:
            cppzip.writestr('libCTRE_PhoenixCCI.so', so_file)
    print(t.green('Unpacked!'))


if __name__ == '__main__':
    main()
