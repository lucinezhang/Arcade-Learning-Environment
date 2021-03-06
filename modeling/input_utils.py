#!/usr/bin/env python

import os, re, threading, time
import numpy as np
from IPython import embed
from scipy import misc
import vip_constants as V

def preprocess_gaze_heatmap(GHmap, sigmaH, sigmaW, bg_prob_density, debug_plot_result=False):
    from scipy.stats import multivariate_normal
    import tensorflow as tf, keras as K # don't move this to the top, as people who import this file might not have keras or tf

    model = K.models.Sequential()

    model.add(K.layers.Lambda(lambda x: x+bg_prob_density, input_shape=(GHmap.shape[1],GHmap.shape[2],1)))

    if sigmaH > 0.0 and sigmaW > 0.0:
        lh, lw = int(4*sigmaH), int(4*sigmaW)
        x, y = np.mgrid[-lh:lh+1:1, -lw:lw+1:1] # so the kernel size is [lh*2+1,lw*2+1]
        pos = np.dstack((x, y))
        gkernel=multivariate_normal.pdf(pos,mean=[0,0],cov=[[sigmaH*sigmaH,0],[0,sigmaW*sigmaW]])
        assert gkernel.sum() > 0.95, "Simple sanity check: prob density should add up to nearly 1.0"

        model.add(K.layers.Lambda(lambda x: tf.pad(x,[(0,0),(lh,lh),(lw,lw),(0,0)],'REFLECT')))
        model.add(K.layers.Conv2D(1, kernel_size=gkernel.shape, strides=1, padding="valid", use_bias=False,
              activation="linear", kernel_initializer=K.initializers.Constant(gkernel)))
    else:
        print "WARNING: Gaussian filter's sigma is 0, i.e. no blur."
    # The following normalization hurts accuracy. I don't know why. But intuitively it should increase accuracy
    # def GH_normalization_and_add_background(x):
    #     max_per_GH = tf.reduce_max(x,axis=[1,2,3])
    #     max_per_GH_correct_shape = tf.reshape(max_per_GH, [tf.shape(max_per_GH)[0],1,1,1])
    #     # normalize values to range [0,1], on a per heap-map basis
    #     x = x/max_per_GH_correct_shape
    #     # add a uniform background 1.0, so that range becomes [1.0,2.0], and background is 2x smaller than max
    #     x = x + 1.0
    #     return x
    # model.add(K.layers.Lambda(lambda x: GH_normalization_and_add_background(x)))
    
    model.compile(optimizer='rmsprop', # not used
          loss='categorical_crossentropy', # not used
          metrics=None)
    output=model.predict(GHmap, batch_size=500)

    if debug_plot_result:
        print r"""debug_plot_result is True. Entering IPython console. You can run:
        %matplotlib
        import matplotlib.pyplot as plt
        f, axarr = plt.subplots(1,2)
        axarr[0].imshow(gkernel)
        rnd=np.random.randint(output.shape[0]); print "rand idx:", rnd
        axarr[1].imshow(output[rnd,...,0])"""
        embed()
    
    shape_before, shape_after = GHmap.shape, output.shape
    assert shape_before == shape_after, """
    Simple sanity check: shape changed after preprocessing. 
    Your preprocessing code might be wrong. Check the shape of output tensor of your tensorflow code above"""
    return output

def frameid_from_filename(fname): 
    """ Extract 'exprname_randnum_23' from '0_blahblah/exprname_randnum_23.png' """

    a, b = os.path.splitext(os.path.basename(fname))
    try:
        exprname, randnum, frameid = a.split('_')
        UTID = exprname + '_' + randnum
    except ValueError as ex:
        raise ValueError("cannot convert filename '%s' to frame ID" % fname)
    return make_unique_frame_id(UTID, frameid)

def make_unique_frame_id(UTID, frameid):
    return (hash(UTID), int(frameid))

def read_gaze_data_asc_file_2(fname):
    """
    Reads a ASC file and returns the following:
    all_gaze (Type:list) A tuple (utid, t, x, y) of all gaze messages in the file.
        where utid is the trial ID to which this gaze belongs. 
        It is extracted from the UTID of the most recent frame
    all_frame (Type:list) A tuple (f_time, frameid, UTID) of all frame messages in the file.
        where f_time is the time of the message. frameid is the unique ID used across the whole project.
    frameid2action (Type: dict) a dictionary mapping frame ID to action label
    (This function is designed to correctly handle the case that the file might be the concatenation of multiple asc files)
    """

    with open(fname, 'r') as f:
        lines = f.readlines()
    frameid, xpos, ypos = "BEFORE-FIRST-FRAME", None, None
    cur_frame_utid = "BEFORE-FIRST-FRAME"
    frameid2action = {frameid: None}
    all_gaze = []
    all_frame = []
    scr_msg = re.compile("MSG\s+(\d+)\s+SCR_RECORDER FRAMEID (\d+) UTID (\w+)")
    freg = "[-+]?[0-9]*\.?[0-9]+" # regex for floating point numbers
    gaze_msg = re.compile("(\d+)\s+(%s)\s+(%s)" % (freg, freg))
    act_msg = re.compile("MSG\s+(\d+)\s+key_pressed atari_action (\d+)")

    for (i,line) in enumerate(lines):
        
        match_sample = gaze_msg.match(line)
        if match_sample:
            g_time, xpos, ypos = int(match_sample.group(1)), match_sample.group(2), match_sample.group(3)
            g_time, xpos, ypos = int(g_time), float(xpos), float(ypos)
            all_gaze.append((cur_frame_utid, g_time, xpos, ypos))
            continue

        match_scr_msg = scr_msg.match(line)
        if match_scr_msg: # when a new id is encountered
            f_time, frameid, UTID = match_scr_msg.group(1), match_scr_msg.group(2), match_scr_msg.group(3)
            f_time = int(f_time)
            cur_frame_utid = UTID
            frameid = make_unique_frame_id(UTID, frameid)
            all_frame.append((f_time, frameid, UTID))
            frameid2action[frameid] = None
            continue

        match_action = act_msg.match(line)
        if match_action:
            timestamp, action_label = match_action.group(1), match_action.group(2)
            if frameid2action[frameid] is None:
                frameid2action[frameid] = int(action_label)
            else:
                print "Warning: there are more than 1 action for frame id %s. Not supposed to happen." % str(frameid)
            continue

    if len(all_frame) < 1000: # simple sanity check
        print "Warning: did you provide the correct ASC file? Because the data for only %d frames is detected" % (len(frameid2pos))
        raw_input("Press any key to continue")

    return all_gaze, all_frame, frameid2action

def read_gaze_data_asc_file(fname):
    """ This function reads a ASC file and returns 
        a dictionary mapping frame ID to a list of gaze positions,
        a dictionary mapping frame ID to action """

    with open(fname, 'r') as f:
        lines = f.readlines()
    frameid, xpos, ypos = "BEFORE-FIRST-FRAME", None, None
    frameid2pos = {frameid: []}
    frameid2action = {frameid: None}
    scr_msg = re.compile("MSG\s+(\d+)\s+SCR_RECORDER FRAMEID (\d+) UTID (\w+)")
    freg = "[-+]?[0-9]*\.?[0-9]+" # regex for floating point numbers
    gaze_msg = re.compile("(\d+)\s+(%s)\s+(%s)" % (freg, freg))
    act_msg = re.compile("MSG\s+(\d+)\s+key_pressed atari_action (\d+)")

    for (i,line) in enumerate(lines):

        match_sample = gaze_msg.match(line)
        if match_sample:
            timestamp, xpos, ypos = match_sample.group(1), match_sample.group(2), match_sample.group(3)
            xpos, ypos = float(xpos), float(ypos)
            frameid2pos[frameid].append((xpos,ypos))
            continue

        match_scr_msg = scr_msg.match(line)
        if match_scr_msg: # when a new id is encountered
            timestamp, frameid, UTID = match_scr_msg.group(1), match_scr_msg.group(2), match_scr_msg.group(3)
            frameid = make_unique_frame_id(UTID, frameid)
            frameid2pos[frameid] = []
            frameid2action[frameid] = None
            continue

        match_action = act_msg.match(line)
        if match_action:
            timestamp, action_label = match_action.group(1), match_action.group(2)
            if frameid2action[frameid] is None:
                frameid2action[frameid] = int(action_label)
            else:
                print "Warning: there are more than 1 action for frame id %s. Not supposed to happen." % str(frameid)
            continue

    frameid2pos[frameid] = [] # throw out gazes after the last frame, because the game has ended but eye tracker keeps recording

    if len(frameid2pos) < 1000: # simple sanity check
        print "Warning: did you provide the correct ASC file? Because the data for only %d frames is detected" % (len(frameid2pos))
        raw_input("Press any key to continue")

    few_cnt = 0
    for v in frameid2pos.values():
        if len(v) < 10: few_cnt += 1
    print "Warning:  %d frames have less than 10 gaze samples. (%.1f%%, total frame: %d)" % \
        (few_cnt, 100.0*few_cnt/len(frameid2pos), len(frameid2pos))
    return frameid2pos, frameid2action

def convert_gaze_pos_to_heap_map(gaze_pos_list, out):
    h,w = out.shape[0], out.shape[1]
    bad_count = 0
    for (x,y) in gaze_pos_list: 
        try:
            out[int(y/V.SCR_H*h), int(x/V.SCR_W*w)] += 1
        except IndexError: # the computed X,Y position is not in the gaze heat map
            bad_count += 1
    return bad_count

def rescale_and_clip_gaze_pos(x,y,RESIZE_H,RESIZE_W):
    isbad=0
    newy, newx = int(y/V.SCR_H*RESIZE_H), int(x/V.SCR_W*RESIZE_W)
    if newx >= RESIZE_W or newx<0:
        isbad = 1
        newx = np.clip(newx, 0, RESIZE_W-1)
    if newy >= RESIZE_H or newy<0:
        isbad = 1
        newy = np.clip(newy, 0, RESIZE_H-1)
    return isbad, newx, newy

class Dataset(object):
  train_imgs, train_lbl, train_fid, train_size = None, None, None, None
  val_imgs, val_lbl, val_fid, val_size = None, None, None, None
  def __init__(self, LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE):
    t1=time.time()
    print "Reading all training data into memory..."
    self.train_imgs, self.train_lbl, self.train_fid = read_np_parallel(LABELS_FILE_TRAIN, RESIZE_SHAPE)
    self.train_size = len(self.train_lbl)
    print "Reading all validation data into memory..."
    self.val_imgs, self.val_lbl, self.val_fid = read_np_parallel(LABELS_FILE_VAL, RESIZE_SHAPE)
    self.val_size = len(self.val_lbl)
    print "Time spent to read train/val data: %.1fs" % (time.time()-t1)

    from collections import defaultdict
    d = defaultdict(int)
    for lbl in self.val_lbl: d[lbl] += 1
    print "Baseline Accuracy (predicting to the majority class label): %.1f%%" % (100.0*max(d.values())/len(self.val_lbl))

    print "Performing standardization (x-mean)..."
    self.standardize()
    print "Done."

  def standardize(self):
    mean = np.mean(self.train_imgs, axis=(0,1,2))
    self.train_imgs -= mean # done in-place --- "x-=mean" is faster than "x=x-mean"
    self.val_imgs -= mean

class Dataset_PastKFrames(Dataset):
  def __init__(self, LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE, K, stride=1, before=0):
    super(Dataset_PastKFrames, self).__init__(LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE)
    self.train_imgs_bak, self.val_imgs_bak = self.train_imgs, self.val_imgs

    t1=time.time()
    self.train_imgs = transform_to_past_K_frames(self.train_imgs, K, stride, before)
    self.val_imgs = transform_to_past_K_frames(self.val_imgs, K, stride, before)
    # Trim labels. This is assuming the labels align with the training examples from the back!!
    # Could cause the model unable to train  if this assumption does not hold
    self.train_lbl = self.train_lbl[-self.train_imgs.shape[0]:]
    self.val_lbl = self.val_lbl[-self.val_imgs.shape[0]:]
    print "Time spent to transform train/val data to pask K frames: %.1fs" % (time.time()-t1)

def transform_to_past_K_frames(original, K, stride, before):
    newdat = []
    for i in range(before+K*stride, len(original)):
        # transform the shape (K, H, W, CH) into (H, W, CH*K)
        cur = original[i-before : i-before-K*stride : -stride] # using "-stride" instead of "stride" lets the indexing include i rather than exclude i
        cur = cur.transpose([1,2,3,0])
        cur = cur.reshape(cur.shape[0:2]+(-1,))
        newdat.append(cur)
        if len(newdat)>1: assert (newdat[-1].shape == newdat[-2].shape) # simple sanity check
    newdat_np = np.array(newdat)
    return newdat_np

class DatasetWithGaze(Dataset):
  frameid2pos, frameid2heatmap, frameid2action_notused = None, None, None
  train_GHmap, val_GHmap = None, None # GHmap means gaze heap map
  
  def __init__(self, LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE, GAZE_POS_ASC_FILE, bg_prob_density, gaussian_sigma):
    super(DatasetWithGaze, self).__init__(LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE)
    print "Reading gaze data ASC file, and converting per-frame gaze positions to heat map..."
    self.frameid2pos, self.frameid2action_notused = read_gaze_data_asc_file(GAZE_POS_ASC_FILE)
    self.train_GHmap = np.zeros([self.train_size, RESIZE_SHAPE[0], RESIZE_SHAPE[1], 1], dtype=np.float32)
    self.val_GHmap = np.zeros([self.val_size, RESIZE_SHAPE[0], RESIZE_SHAPE[1], 1], dtype=np.float32)

    # Prepare train val gaze data
    print "Running convert_gaze_pos_to_heap_map() and convolution..."
    # Assign a heap map for each frame in train and val dataset
    t1 = time.time()
    bad_count, tot_count = 0, 0
    for (i,fid) in enumerate(self.train_fid):
        tot_count += len(self.frameid2pos[fid])
        bad_count += convert_gaze_pos_to_heap_map(self.frameid2pos[fid], out=self.train_GHmap[i])
    for (i,fid) in enumerate(self.val_fid):
        tot_count += len(self.frameid2pos[fid])
        bad_count += convert_gaze_pos_to_heap_map(self.frameid2pos[fid], out=self.val_GHmap[i])
    print "Bad gaze (x,y) sample: %d (%.2f%%, total gaze sample: %d)" % (bad_count, 100*float(bad_count)/tot_count, tot_count)    
    print "'Bad' means the gaze position is outside the 160*210 screen"

    sigmaH = gaussian_sigma * RESIZE_SHAPE[0] / 210.0
    sigmaW = gaussian_sigma * RESIZE_SHAPE[1] / 160.0
    self.train_GHmap = preprocess_gaze_heatmap(self.train_GHmap, sigmaH, sigmaW, bg_prob_density)
    self.val_GHmap = preprocess_gaze_heatmap(self.val_GHmap, sigmaH, sigmaW, bg_prob_density)
    print "Done. convert_gaze_pos_to_heap_map() and convolution used: %.1fs" % (time.time()-t1)

class DatasetCenteredAtLastGaze(Dataset):
    frameid2pos, frameid2action_notused = None, None

    def __init__(self, LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE, GAZE_POS_ASC_FILE, K=1, stride=1, before=0):
        super(DatasetCenteredAtLastGaze, self).__init__(LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE)
        self.RESIZE_SHAPE = RESIZE_SHAPE
        print "Reading gaze data ASC file..."
        self.frameid2pos, self.frameid2action_notused = read_gaze_data_asc_file(GAZE_POS_ASC_FILE)
        print "Running rescale_and_clip_gaze_pos_on_frameid2pos()..."
        self.rescale_and_clip_gaze_pos_on_frameid2pos(self.frameid2pos)

        print  "Running center_img_at_gaze() on train/val data..."
        rev = lambda (x,y): (y,x)
        last_gaze_of = lambda gaze_pos_list: rev(gaze_pos_list[-1]) if gaze_pos_list else (RESIZE_SHAPE[0]/2, RESIZE_SHAPE[1]/2)
        self.train_gaze_y_x = np.asarray([last_gaze_of(self.frameid2pos[fid]) for fid in self.train_fid])
        self.train_imgs = self.center_img_at_gaze(self.train_imgs, self.train_gaze_y_x)
        self.val_gaze_y_x = np.asarray([last_gaze_of(self.frameid2pos[fid]) for fid in self.val_fid])
        self.val_imgs = self.center_img_at_gaze(self.val_imgs, self.val_gaze_y_x)    

        print  "Making past-K-frame train/val data..."
        t1=time.time()
        self.train_imgs = transform_to_past_K_frames(self.train_imgs, K, stride, before)
        self.val_imgs = transform_to_past_K_frames(self.val_imgs, K, stride, before)
        # Trim labels. This is assuming the labels align with the training examples from the back!!
        # Could cause the model unable to train  if this assumption does not hold
        self.train_lbl = self.train_lbl[-self.train_imgs.shape[0]:]
        self.val_lbl = self.val_lbl[-self.val_imgs.shape[0]:]
        print "Time spent to transform train/val data to pask K frames: %.1fs" % (time.time()-t1)
  
    def rescale_and_clip_gaze_pos_on_frameid2pos(self, frameid2pos):
        bad_count, tot_count = 0, 0
        for fid in frameid2pos:
            gaze_pos_list = frameid2pos[fid]
            tot_count += len(gaze_pos_list)
            for (i, (x, y)) in enumerate(gaze_pos_list):
                isbad, newx, newy = rescale_and_clip_gaze_pos(x,y,self.RESIZE_SHAPE[0],self.RESIZE_SHAPE[1])
                bad_count += isbad
                gaze_pos_list[i] = (newx, newy)  
        print "Bad gaze (x,y) sample: %d (%.2f%%, total gaze sample: %d)" % (bad_count, 100*float(bad_count)/tot_count, tot_count)    
        print "'Bad' means the gaze position is outside the 160*210 screen"

    def center_img_at_gaze(self, frame_dataset, gaze_y_x_dataset, debug_plot_result=False):
        import tensorflow as tf, keras as K # don't move this to the top, as people who import this file might not have keras or tf
        import keras.layers as L
        gaze_y_x = L.Input(shape=(2,))
        imgs = L.Input(shape=(frame_dataset.shape[1:]))
        h, w = frame_dataset.shape[1:3]
        c_img = L.ZeroPadding2D(padding=(h,w))(imgs)
        c_img = L.Lambda(lambda x: tf.image.extract_glimpse(x, size=(2*h,2*w), offsets=(gaze_y_x+(h,w)), centered=False, normalized=False))(c_img)
        # c_img = L.Lambda(lambda x: tf.image.resize_images(x, size=(h,w)))(c_img)

        model=K.models.Model(inputs=[imgs, gaze_y_x], outputs=[c_img])
        model.compile(optimizer='rmsprop', # not used
          loss='categorical_crossentropy', # not used
          metrics=None)
        output=model.predict([frame_dataset, gaze_y_x_dataset], batch_size=500)
        if debug_plot_result:
            print r"""debug_plot_result is True. Entering IPython console. You can run:
            %matplotlib
            import matplotlib.pyplot as plt
            plt.style.use('grayscale')
            f, axarr = plt.subplots(1,2)
            rnd=np.random.randint(output.shape[0]); print "rand idx:", rnd
            axarr[0].imshow(frame_dataset[rnd,...,0])
            axarr[1].imshow(output[rnd,...,0])"""
            embed()

        return output

def read_np_parallel(label_file, RESIZE_SHAPE, num_thread=6):
    """
    Read the whole dataset into memory. 
    Remember to run "imgs.nbytes" to see how much memory it uses
    Provide a label file (text file) which has "{image_path} {label}\n" per line.
    Returns a numpy array of the images, and a numpy array of labels
    """
    labels, fids = [], []
    png_files = []
    with open(label_file,'r') as f:
        for line in f:
            line=line.strip()
            if line.startswith("#") or line == "": 
                continue # skip comments or empty lines
            fname, lbl = line.split(' ')
            png_files.append(fname)
            labels.append(int(lbl))
            fids.append(frameid_from_filename(fname))
    N = len(labels)
    imgs = np.empty((N,RESIZE_SHAPE[0],RESIZE_SHAPE[1],1), dtype=np.float32)
    labels = np.asarray(labels, dtype=np.int32)

    def read_thread(PID):
        d = os.path.dirname(label_file)
        for i in range(PID, N, num_thread):
            img = misc.imread(os.path.join(d, png_files[i]), 'Y') # 'Y': grayscale
            img = misc.imresize(img, [RESIZE_SHAPE[0],RESIZE_SHAPE[1]], interp='bilinear')
            img = np.expand_dims(img, axis=2)
            img = img.astype(np.float32) / 255.0
            imgs[i,:] = img

    o=ForkJoiner(num_thread=num_thread, target=read_thread)
    o.join()
    return imgs, labels, fids

class ForkJoiner():
    def __init__(self, num_thread, target):
        self.num_thread = num_thread
        self.threads = [threading.Thread(target=target, args=[PID]) for PID in range(num_thread)]
        for t in self.threads: 
            t.start()
    def join(self):
        for t in self.threads: t.join()

class Dataset_PastKFramesByTime(Dataset):
  def __init__(self, LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE, GAZE_POS_ASC_FILE, K, stride=1, ms_before=0):
    super(Dataset_PastKFramesByTime, self).__init__(LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE)
    self.train_imgs_bak, self.val_imgs_bak = self.train_imgs, self.val_imgs

    def data_is_sorted_by_timestamp(fid_list):
        # It does (1) stable sort (2) ignore and only compare the second key (i.e.frame number)
        sorted_fid_list = sorted(fid_list,cmp=lambda x,y:int(x[0]==y[0])*(x[1]-y[1])) 
        return sorted_fid_list == fid_list
    assert data_is_sorted_by_timestamp(self.train_fid)
    assert data_is_sorted_by_timestamp(self.val_fid)
    # Since later code extracts adjacant indice of the data via something like img[100:104], "data_is_sorted_by_timestamp" must be true.
    # (self.train/val_fid is a list that stores the corresponding frame ID of self.train/val_imgs)
    # If assertion failed, rewrite the dataset generation python file to satify this assumption

    t1=time.time()
    print "Reading gaze data ASC file..."
    _, all_frame, frameid2action = read_gaze_data_asc_file_2(GAZE_POS_ASC_FILE)
    print "Done."
    self.train_imgs, self.train_lbl = transform_to_past_K_frames_ByTime(self.train_imgs, self.train_fid, all_frame, frameid2action, K, stride, ms_before)
    self.val_imgs, self.val_lbl = transform_to_past_K_frames_ByTime(self.val_imgs, self.val_fid, all_frame, frameid2action, K, stride, ms_before)
    print "Time spent to transform train/val data to pask K frames: %.1fs" % (time.time()-t1)

def transform_to_past_K_frames_ByTime(frame_dataset, frame_fid_list, all_frame, frameid2action, K, stride, ms_before):
    newdat = []
    newlbl = []
    frameid2time = {frameid:f_time for (f_time, frameid, UTID) in all_frame}
    time = [frameid2time[fid] for fid in frame_fid_list] # find the timestamp for each frame in frame_dataset

    l, r = 0, None # two pointers: left, right
    for r in range(K*stride, len(frame_dataset)):

        # move l to the correct position
        if frame_fid_list[l][0] != frame_fid_list[r][0]: 
            l=r # [0] is UTID. If not equal, l and r are in different trials; so time[l] and time[r] is incomparable; so we need to set l=r.
        while l<r and time[r] - time[l+1] >= ms_before: 
            l+=1

        leftmost = l-K*stride # do some check to make the line "cur = frame_dataset[l : l-K*stride : -stride]" below work correctly
        if leftmost<0 or frame_fid_list[leftmost][0] != frame_fid_list[r][0]:  
        # the leftmost idx is not a valid idx, or is in a different trial than current frame (the frame with idx r)
            continue

        # transform the shape (K, 84, 84, CH) into (84, 84, CH*K)
        cur = frame_dataset[l : l-K*stride : -stride] # using "-stride" instead of "stride" lets the indexing include l rather than exclude l
        cur = cur.transpose([1,2,3,0])
        cur = cur.reshape(cur.shape[0:2]+(-1,))

        newdat.append(cur)
        newlbl.append(frameid2action[frame_fid_list[r]])
        if len(newdat)>1: assert (newdat[-1].shape == newdat[-2].shape) # simple sanity check
    newdat_np = np.array(newdat)
    newlbl_np = np.array(newlbl, dtype=np.int32)
    return newdat_np, newlbl_np

class DatasetWithGazeWindow(Dataset):
    def __init__(self, LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE, GAZE_POS_ASC_FILE, bg_prob_density, gaussian_sigma,
        window_left_bound_ms=1000, window_right_bound_ms=0):
      super(DatasetWithGazeWindow, self).__init__(LABELS_FILE_TRAIN, LABELS_FILE_VAL, RESIZE_SHAPE)
      self.RESIZE_SHAPE = RESIZE_SHAPE
      self.bg_prob_density = bg_prob_density
      self.gaussian_sigma=gaussian_sigma
      self.window_left_bound, self.window_right_bound = window_left_bound_ms, window_right_bound_ms
      print "Reading gaze data ASC file, and converting per-frame gaze positions to heat map..."
      all_gaze, all_frame, _ = read_gaze_data_asc_file_2(GAZE_POS_ASC_FILE)
      self.rescale_and_clip_gaze_pos_on_all_gaze(all_gaze)
      self.train_GHmap = np.empty([self.train_size, RESIZE_SHAPE[0], RESIZE_SHAPE[1], 1], dtype=np.float32)
      self.val_GHmap = np.empty([self.val_size, RESIZE_SHAPE[0], RESIZE_SHAPE[1], 1], dtype=np.float32)
      print "Running convert_gaze_data_to_map()..."
      t1=time.time()
      self.frameid2GH, self.frameid2gazetuple = self.convert_gaze_data_to_heat_map_proprietary(all_gaze, all_frame)
      self.prepare_train_val_gaze_data()
      print "Done. convert_gaze_data_to_heat_map() and convolution used: %.1fs" % (time.time()-t1)
      
    def prepare_train_val_gaze_data(self):
        print "Assign a heap map for each frame in train and val dataset..."
        for (i,fid) in enumerate(self.train_fid):
            self.train_GHmap[i] = self.frameid2GH[fid]
        for (i,fid) in enumerate(self.val_fid):
            self.val_GHmap[i] = self.frameid2GH[fid]
        print "Applying Gaussian Filter and normalization on train/val gaze heat map..."
        sigmaH = self.gaussian_sigma * self.RESIZE_SHAPE[0] / 210.0
        sigmaW = self.gaussian_sigma * self.RESIZE_SHAPE[1] / 160.0
        self.train_GHmap = preprocess_gaze_heatmap(self.train_GHmap, sigmaH, sigmaW, self.bg_prob_density)
        self.val_GHmap = preprocess_gaze_heatmap(self.val_GHmap, sigmaH, sigmaW, self.bg_prob_density)

    def rescale_and_clip_gaze_pos_on_all_gaze(self, all_gaze):
        bad_count=0
        for (i, (utid, t, x, y)) in enumerate(all_gaze):
            isbad, newx, newy = rescale_and_clip_gaze_pos(x,y,self.RESIZE_SHAPE[0],self.RESIZE_SHAPE[1])
            bad_count += isbad
            all_gaze[i] = (utid, t, newx, newy)

        print "Bad gaze (x,y) sample: %d (%.2f%%, total gaze sample: %d)" % (bad_count, 100*float(bad_count)/len(all_gaze), len(all_gaze))
        print "'Bad' means the gaze position is outside the 160*210 screen"

    def convert_gaze_data_to_heat_map_proprietary(self, all_gaze, all_frame):
        GH = np.zeros([self.RESIZE_SHAPE[0], self.RESIZE_SHAPE[1], 1], dtype=np.float32)
        left, right = 0,0
        frameid2GH = {}
        frameid2gazetuple={}

        def left_matched(utid, frame_utid, gaze_t, frame_t, window_left_bound):
            if frame_t  - gaze_t > window_left_bound: return False
            elif utid != frame_utid: return False
            else: return True

        def right_matched(utid, frame_utid, gaze_t, frame_t, window_right_bound):
            if frame_t - gaze_t > window_right_bound: return False
            elif utid != frame_utid: return False
            else: return True

        for (frame_t, frameid, frame_utid) in all_frame:

            while right<len(all_gaze):
                utid, gaze_t, x, y = all_gaze[right] 
                if right_matched(utid, frame_utid, gaze_t, frame_t, self.window_right_bound): break
                GH[y,x,0] += 1.0 
                right+=1 

            while left<right:
                utid, gaze_t, x, y = all_gaze[left]
                if left_matched(utid, frame_utid, gaze_t, frame_t, self.window_left_bound): break
                GH[y,x,0] -= 1.0
                left+=1 

            gaze_for_cur_frame = all_gaze[left:right]
            if gaze_for_cur_frame: # non-empty
                assert gaze_for_cur_frame[-1][1] < frame_t # simple sanity-check: the timestamp of the latest gaze position should be smaller than the timestamp of current frame

            frameid2GH[frameid] = GH.copy()
            frameid2gazetuple[frameid] = gaze_for_cur_frame

        return frameid2GH, frameid2gazetuple
