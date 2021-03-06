#!/usr/bin/env python

import sys, re, tarfile, os, shutil, subprocess, threading
from input_utils import read_gaze_data_asc_file, frameid_from_filename
from IPython import embed

def untar(tar_path, output_path):
    tar = tarfile.open(tar_path, 'r')
    tar.extractall(output_path)
    png_files = [png for png in tar.getnames() if png.endswith('.png')]
    png_files = sorted(png_files,key=frameid_from_filename)
    return png_files

def old_ver_create_for_only_one_trial():
    asc_file, tar_file, output_path, percent = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
    
    print "Reading asc file..."
    _, frameid2action = read_gaze_data_asc_file(asc_file)

    print "Untaring file..."
    png_files = untar(tar_file, output_path)

    print "Generating train/val label files..."
    xy_str = []
    for png in png_files:
        fid = frameid_from_filename(png)
        if fid in frameid2action and frameid2action[fid] != None:
            xy_str.append('%s %d' % (png, frameid2action[fid]))
        else:
            print "Warning: Cannot find the label for frame ID %s. Skipping this frame." % str(fid)
    
    xy_str_train = xy_str[:int(percent*len(xy_str))]
    xy_str_val =   xy_str[int(percent*len(xy_str)):]
    #asc_filename, _ = os.path.splitext(os.path.basename(asc_file))
    tar_filename, _ = os.path.splitext(os.path.basename(tar_file))
    train_file_name = output_path + "/" + tar_filename + '-train.txt'
    val_file_name =   output_path + "/" + tar_filename + '-val.txt'

    with open(train_file_name, 'w') as f:
        f.write('\n'.join(xy_str_train))
        f.write('\n')

    with open(val_file_name, 'w') as f:
        f.write('\n'.join(xy_str_val))
        f.write('\n')

    shutil.copyfile(asc_file, output_path+'/'+os.path.basename(asc_file))

    print "Copied ASC file to ", output_path
    print "Done. Outputs are:\n %s (%d examples)\n %s (%d examples)" % (train_file_name, len(xy_str_train), val_file_name, len(xy_str_val))

def new_ver_use_spec_file():

    print "Reading dataset specification file..."
    spec_file, dataset_name, output_path = sys.argv[2], sys.argv[3], sys.argv[4]
    lines = []
    with open(spec_file,'r') as f:
        for line in f:
            if line.strip().startswith("#") or line == "": 
                continue # skip comments or empty lines
            lines.append(line)
    spec = '\n'.join(lines)
    import ast
    spec = ast.literal_eval(spec)
    # some simple sanity checks
    assert isinstance(spec,list)
    for fname in [e['TAR'] for e in spec] + [e['ASC'] for e in spec]:
        if not os.path.exists(fname): 
            raise IOError("No such file: %s" % fname)
    
    print "Untaring files in parallel..."
    png_files_each=[None]*len(spec)
    def untar_thread(PID):
        png_files_each[PID] = untar(spec[PID]['TAR'], output_path)
    untar_work=ForkJoiner(num_thread=len(spec), target=untar_thread)

    print "Reading asc files while untaring..."
    frameid2action_each=[None]*len(spec)
    for i in range(len(spec)):
        _, frameid2action_each[i] = read_gaze_data_asc_file(spec[i]['ASC'])

    print "Concatenating asc file while untaring..."
    asc_filename = output_path+'/'+dataset_name+'.asc'
    with open(asc_filename, 'w') as f:
        subprocess.call(['cat']+[entry['ASC'] for entry in spec], stdout=f)
    print "Waiting for untaring to finish..."
    untar_work.join()

    print "Generating train/val label files..."
    xy_str_train = []
    xy_str_val =   []
    for i in range(len(spec)):
        # prepare xy_str[] --- all (example, label) strings
        xy_str = []
        for png in png_files_each[i]:
            fid = frameid_from_filename(png)
            if fid in frameid2action_each[i] and frameid2action_each[i][fid] != None:
                xy_str.append('%s %d' % (png, frameid2action_each[i][fid]))
            else:
                print "Warning: Cannot find the label for frame ID %s. Skipping this frame." % str(fid)
        
        # assign each xy_str to the train/val part of the dataset
        def assign(range_list, target):
            # sort the ranges using left bound as key (e.g. ["0.5-1", "0-0.2"] becomes ["0-0.2", "0.5-1"])
            # A must, because Dataset_PastKFramesByTime in input_utils.py assert data_is_sorted_by_timestamp()
            range_list=sorted(range_list, key=lambda x: float(x.split('-')[0]))
            for range_ in range_list:
                l, r = range_.split('-')
                l, r = float(l), float(r)
                target.extend(xy_str[int(l*len(xy_str)):int(r*len(xy_str))])
        assign(spec[i]['TRAIN'], xy_str_train)
        assign(spec[i]['VAL'], xy_str_val)

    train_file_name = output_path + "/" + dataset_name + '-train.txt'
    val_file_name =   output_path + "/" + dataset_name + '-val.txt'

    with open(train_file_name, 'w') as f:
        f.write('# ' + '# '.join(lines) + '\n') # echo spec file content
        f.write('\n'.join(xy_str_train))
        f.write('\n')

    with open(val_file_name, 'w') as f:
        f.write('# ' + '# '.join(lines) + '\n') # echo spec file content
        f.write('\n'.join(xy_str_val))
        f.write('\n')

    print "\nDone. Outputs are:"
    print " %s" % asc_filename
    print " %s (%d examples)" % (train_file_name, len(xy_str_train))
    print " %s (%d examples)" % (val_file_name, len(xy_str_val))
    print "For convenience, dataset specification is also prepended to train/val text file."


class ForkJoiner():
    def __init__(self, num_thread, target):
        self.num_thread = num_thread
        self.threads = [threading.Thread(target=target, args=[PID]) for PID in range(num_thread)]
        for t in self.threads: 
            t.start()
    def join(self):
        for t in self.threads: t.join()

if __name__ == '__main__':
    if len(sys.argv)<5:
        print "Usage: "
        print "  %s --spec text_file(see dataset_specification_example.txt) dataset_name(give a name to this dataset)  output_path(e.g. a directory called 'dataset')\n"  % sys.argv[0]
        print "  Old version; it can only create for one trial:"
        print "  %s asc_file tar_file output_path(e.g. a directory called 'dataset') training_data_percentage(float, range [0.0, 1.0])" % sys.argv[0]
        sys.exit(0)
    if sys.argv[1] != '--spec':
        old_ver_create_for_only_one_trial()
    else:
        new_ver_use_spec_file()
