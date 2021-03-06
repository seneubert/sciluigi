import luigi
import sciluigi as sl
import math
from subprocess import call
import subprocess as sub
import sys
import requests
import time

# ------------------------------------------------------------------------
# Task classes
# ------------------------------------------------------------------------

#Rsync a folder
class RSyncAFolder(sl.Task):
    src_dir_path = luigi.Parameter()
    dest_dir_path = luigi.Parameter()

    def output(self):
        # TODO: Let's see if a folder can be used as a target ...
        return sl.create_file_targets(
            dest_dir = self.dest_dir_path)

    def run(self):
        call('rsync -a {src}/ {dest}/'.format(
            src = self.src_dir_path,
            dest = self.dest_dir_path),
        shell=True)


#Run a program that takes 10 minutes (seconds now, for a try) to run
class Run10MinuteSleep(sl.Task):
    upstream = sl.TargetSpecParameter()

    def output(self):
        return sl.create_file_targets(
            doneflag = self.input('upstream').path + '.10mintask_done')

    def run(self):
        time.sleep(10)
        with self.output()['doneflag'].open('w') as flagfile:
            flagfile.write('Done!')


#Perform a web request
class DoWebRequest(sl.Task):
    upstream = sl.TargetSpecParameter()

    def output(self):
        return sl.create_file_targets(
            doneflag = self.input('upstream').path + '.webrequest_done')

    def run(self):
        resp = requests.get('http://bils.se')
        if resp.status_code != 200:
            raise Exception('Web request failed!')
            sys.exit()
        else:
            with self.output()['doneflag'].open('w') as flagfile:
                flagfile.write('Web Request Task Done!')


#Split a file
class ExistingData(sl.ExternalTask):
    file_name = luigi.Parameter(default='acgt.txt')

    def output(self):
        return sl.create_file_targets(
             acgt = 'data/' + self.file_name)

class SplitAFile(sl.Task):
    indata = sl.TargetSpecParameter()

    def output(self):
        return sl.create_file_targets(
            part1 = self.input('indata').path + '.part1',
            part2 = self.input('indata').path + '.part2')


    def run(self):
        cmd = 'wc -l {f}'.format(f=self.get_path('indata') )
        wc_output = sub.check_output(cmd, shell=True)
        lines_cnt = int(wc_output.split(' ')[0])
        head_cnt = int(math.ceil(lines_cnt / 2))
        tail_cnt = int(math.floor(lines_cnt / 2))

        cmd_head = 'head -n {cnt} {i} > {part1}'.format(
            i=self.get_path('indata'),
            cnt=head_cnt,
            part1=self.output()['part1'].path)
        print("COMMAND: " + cmd_head)
        sub.call(cmd_head, shell=True)

        sub.call('tail -n {cnt} {i} {cnt} > {part2}'.format(
            i=self.get_path('indata'),
            cnt=tail_cnt,
            part2=self.output()['part2'].path),
        shell=True)


#Run the same program on both parts of the split
class DoSomething(sl.Task):
    indata = sl.TargetSpecParameter()

    def output(self):
        return sl.create_file_targets(
            outdata = self.get_path('indata') + '.something_done')

    def run(self):
        with self.input('indata').open() as infile, self.output()['outdata'].open('w') as outfile:
            for line in infile:
                outfile.write(line.lower() + '\n')


#Merge the results of the programs
class MergeFiles(sl.Task):
    part1 = sl.TargetSpecParameter()
    part2 = sl.TargetSpecParameter()

    def output(self):
        return sl.create_file_targets(
            merged = self.input('part1').path + '.merged'
        )

    def run(self):
        sub.call('cat {f1} {f2} > {out}'.format(
            f1=self.input('part1').path,
            f2=self.input('part2').path,
            out=self.output()['merged'].path),
        shell=True)

# ------------------------------------------------------------------------
# Workflow class
# ------------------------------------------------------------------------

class DahlbergTest(sl.WorkflowTask):

    task = luigi.Parameter()

    def requires(self):

        tasks = {}

        # Workflow definition goes here!

        # Rsync a folder
        tasks['rsync'] = RSyncAFolder(
                src_dir_path = 'data',
                dest_dir_path = 'data_rsynced_copy')

        # Run a program that takes 10 minutes (seconds)
        tasks['run10min'] = Run10MinuteSleep(
                upstream = tasks['rsync'].outspec('dest_dir'))

        # Do a web request
        tasks['webreq'] = DoWebRequest(
                upstream = tasks['run10min'].outspec('doneflag'))

        tasks['rawdata'] = ExistingData()

        # Split a file
        tasks['split'] = SplitAFile(
                indata = tasks['rawdata'].outspec('acgt'))

        # Run the same task on the two splits
        tasks['dosth1'] = DoSomething(
                indata = tasks['split'].outspec('part1'))

        tasks['dosth2'] = DoSomething(
                indata = tasks['split'].outspec('part2'))

        # Merge the results
        tasks['merge'] = MergeFiles(
                part1 = tasks['dosth1'].outspec('outdata'),
                part2 = tasks['dosth2'].outspec('outdata'))

        return tasks[self.task]


# ------------------------------------------------------------------------
# Run this file as a script
# ------------------------------------------------------------------------

if __name__ == '__main__':
    luigi.run()
