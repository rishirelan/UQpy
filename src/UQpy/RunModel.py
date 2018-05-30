import os
import numpy as np
import sys


class RunModel:

    """
    A class used to run a computational model a specified sample points.

    This class takes samples, either passed as a variable or read through a text file, and runs a specified
    computational model at those sample points. This can be done by either passing variables and running entirely in
    python or by calling shell scripts that run a third-party software model.

    Input:
    :param samples: The sample values at which the model will be evaluated. Samples can be passed directly as an array
                        or can be passed through the text file 'UQpy_Samples.txt'. If passing samples via text file, set
                        samples = None or do not set the samples input.
    :type samples: numpy array

    :param dimension: The dimension of the random variable whose samples are being passed to the model.
    :type dimension: int

    :param model_type: Define the model as a python file or as a third party software model (e.g. Matlab, Abaqus, etc.)
            Options: None - Run a third party software model
                     'python' - Run a python model. When selected, the python file must contain a class RunPythonModel
                                that takes, as input, samples and dimension and returns quantity of interest (qoi) in
                                in list form where there is one item in the list per sample. Each item in the qoi list
                                may take type the user prefers.
            Default: None
    :type model_type: str

    :param model_script: Defines the script (must be either a shell script (.sh) or a python script (.py)) used to call
                            the model.
                         This is a user-defined script that must be provided.
                         If model_type = 'python', this must be a python script (.py) having a specified class
                            structure. Details on this structure can be found in the UQpy documentation.
    :type: model_script: str

    :param input_script: Defines the script (must be either a shell script (.sh) or a python script (.py)) that takes
                            samples generated by UQpy from the sample file generated by UQpy (UQpy_run_{0}.txt) and
                            imports them into a usable input file for the third party solver. Details on
                            UQpy_run_{0}.txt can be found in the UQpy documentation.
                         If model_type = None, this is a user-defined script that the user must provide.
                         If model_type = 'python', this is not used.
    :type: input_script: str

    :param output_script: (Optional) Defines the script (must be either a shell script (.sh) or python script (.py))
                            that extracts quantities of interest from third-party output files and saves them to a file
                            (UQpy_eval_{}.txt) that can be read for postprocessing and adaptive sampling methods by
                            UQpy.
                          If model_type = None, this is an optional user-defined script. If not provided, all run files
                            and output files will be saved in the folder 'UQpyOut' placed in the current working
                            directory. If provided, the text files UQpy_eval_{}.txt are placed in this directory and all
                            other files are deleted.
                          If model_type = 'python', this is not used.
    :type output_script: str

    :param cpu: Number of CPUs over which to run the job.
                UQpy distributes the total number of model evaluations over this number of CPUs
                Default: 1 - Runs serially
    :type cpu: int

    Output:
    :param model_eval: An instance of a sub-class that contains the model solutions. Depending on how the model is run,
                            model_eval is an instance of a different class.
                       If model_type = 'python', model_eval is an instance of the class RunPythonModel defined in the
                            python model_script.
                       If model_type = 'None' and cpu <= 1, model_eval is an instance of the class RunSerial
                       If model_type = 'None' and cpu > 1, model_eval is an instance of the class RunParallel
                       Regardless of model_type, model_eval has the following key attributes:
                            model_eval.samples = Sample values at which the model has been run.
                            model_eval.QOI = Solution of the model at each sample value.
    :type: model_eval: The two key attributes of model_eval have the following type.
                       model_eval.samples = numpy array
                       model_eval.QOI = list
    """

    # Authors: Dimitris Giovanis, Michael D. Shields
    # Updated: 5/1/18 by Michael D. Shields & Dimitris Giovanis

    def __init__(self, samples=None, dimension=None, model_type=None, model_script=None, input_script=None,
                 output_script=None,  cpu=None):

        self.CPUs = cpu
        self.model_type = model_type
        self.model_script = model_script
        self.input_script = input_script
        self.output_script = output_script
        self.dimension = dimension
        self.model_eval = []

        # If samples=None, then samples must be imported from UQpy_Samples.txt. Load the file and assign the samples to
        # 'self.samples'. Otherwise, read the samples as input.
        if samples is None and os.path.isfile('UQpy_Samples.txt'):
            self.samples = np.loadtxt('UQpy_Samples.txt', dtype=np.float32)
            if self.samples.ndim == 1:
                if self.dimension == 1:
                    self.samples = self.samples.reshape(self.samples.shape[0], self.dimension)
                else:
                    self.samples = self.samples.reshape(1, self.samples.shape[0])
        elif samples is not None:
            self.samples = samples
        else:
            raise ValueError('Samples must be provided either as input to RunModel or from UQpy_Samples.txt')

        ################################################################################################################
        # Run a python model by importing the user-specified model_script file
        # model_script must contain a class RunPythonModel - See documentation for details.
        if self.model_type == 'python':
            # Check that the script is a python file
            if not self.model_script.lower().endswith('.py'):
                raise ValueError('A python script, with extension .py, must be provided.')

            model_script = self.model_script[:-3]
            python_model = __import__(model_script)
            print("\nEvaluating the model...\n")
            self.model_eval = python_model.RunPythonModel(self.samples, self.dimension)

        ################################################################################################################
        # Run a third-party software model with file-passing
        elif self.model_type is None:
            import shutil
            current_dir = os.getcwd()

            ############################################################################################################
            # Create a unique temporary directory 'tmp'.
            # Run the model from this directory.
            # Move the data generated by the model to the directory 'UQpyOut'
            # Remove 'tmp' after completion.

            folder_name = 'UQpyOut'
            output_directory = os.path.join(os.sep, current_dir, folder_name)

            # Create a list of all of the working files
            model_files = list()
            for fname in os.listdir(current_dir):
                path = os.path.join(current_dir, fname)
                if not os.path.isdir(path):
                    model_files.append(path)

            # Create tmp directory
            dir_path = os.path.join(current_dir, 'tmp')
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                shutil.rmtree(dir_path)
            os.makedirs('tmp', exist_ok=False)
            work_dir = os.path.join(os.sep, current_dir, 'tmp')

            # Copy files from the model list to tmp
            for file_name in model_files:
                full_file_name = os.path.join(current_dir, file_name)
                shutil.copy(full_file_name, work_dir)

            # Change current working directory to tmp
            os.chdir(os.path.join(current_dir, work_dir))

            # Check for parallel or serial processing
            if self.CPUs != 1 and self.CPUs is not None:
                parallel_processing = True
                import multiprocessing
                n_cpu = multiprocessing.cpu_count()
                if self.CPUs > n_cpu:
                    print("Error: You have available {0:1d} CPUs. Start parallel computing ..."
                          "using {0:1d} CPUs".format(n_cpu))
                    self.CPUs = n_cpu
            else:
                parallel_processing = False

            # Run the model
            print("\nEvaluating the model...\n")
            if parallel_processing is True:
                self.model_eval = self.RunParallel(samples=self.samples, cpu=self.CPUs, dimension=self.dimension,
                                                   model_script=self.model_script, input_script=self.input_script,
                                                   output_script=self.output_script)
            else:
                if self.output_script is not None:
                    self.model_eval = self.RunSerial(samples=self.samples, dimension=self.dimension,
                                                     model_script=self.model_script, input_script=self.input_script,
                                                     output_script=self.output_script)
                else:
                    self.RunSerial(self.samples)

            # Move the data to directory UQpyOut
            os.makedirs(output_directory, exist_ok=True)

            path = os.path.join(current_dir, work_dir)

            if self.output_script is not None:
                src_files = [filename for filename in os.listdir(path) if filename.startswith("UQpy_eval_")]

                for file_name in src_files:
                    full_file_name = os.path.join(path, file_name)
                    shutil.copy(full_file_name, output_directory)
            else:
                src_files = [filename for filename in os.listdir(path)]

                for file_name in src_files:
                    full_file_name = os.path.join(path, file_name)
                    shutil.copy(full_file_name, output_directory)

            # Delete the tmp working directory
            shutil.rmtree(work_dir)
            os.chdir(current_dir)

    ####################################################################################################################
    class RunSerial:

        """
        A subclass of RunModel to run a third-party software model serially (without parallel processing).

        Most attributes of this subclass are inherited from RunModel. The only variable that is not inherited is QOI.

        Input:
        :param samples: Inherited from RunModel. See its documentation.
        :type samples: numpy array

        :param dimension: Inherited from RunModel. See its documentation.
        :type dimension: int

        :param model_script: Inherited from RunModel. See its documentation.
        :type: model_script: str

        :param input_script: Inherited from RunModel. See its documentation.
        :type: input_script: str

        :param output_script: Inherited from RunModel. See its documentation.
        :type output_script: str

        Output:
        :param QOI: List containing the Quantity of Interest from the simulations
                    Each item in the list corresponds to one simulation
        :type QOI: list
                    Each item in the list may be of arbitrary data type (e.g. int, float, nparray, etc.)
        """

        # Authors: Dimitris Giovanis, Michael D. Shields
        # Updated: 5/1/18 by Michael D. Shields & Dimitris Giovanis

        def __init__(self, samples=None, dimension=None, model_script=None, input_script=None, output_script=None):

            self.dimension = dimension
            self.model_script = model_script
            self.input_script = input_script
            self.output_script = output_script
            self.samples = samples
            self.QOI = []

            for i in range(self.samples.shape[0]):

                # Write each value of UQpy_Samples.txt (self.samples) into a separate *.txt file
                with open('UQpy_run_{0}.txt'.format(i), 'wb') as f:
                    np.savetxt(f, self.samples[i, :], fmt='%0.5f')

                # Run input_script to create the input file for the model
                # input_script is a user defined script that converts UQpy_run_{0}.txt into a usable input file for
                #   third party software.
                if self.input_script.lower().endswith('.sh'):
                    join_input_script = './{0} {1}'.format(self.input_script, i)
                    os.system(join_input_script)
                elif self.input_script.lower().endswith('.py'):
                    join_input_script = 'python {0} {1}'.format(self.input_script, i)
                    os.system(join_input_script)
                else:
                    print('Unrecognized script type. Options are shell script (.sh) or python script (.py).')
                    sys.exit()

                # Run model_script to run the model
                # model_script is a user defined script that calls the third-party model.
                if self.model_script.lower().endswith('.sh'):
                    join_model_script = './{0} {1}'.format(self.model_script, i)
                    os.system(join_model_script)
                elif self.model_script.lower().endswith('.py'):
                    join_model_script = 'python {0} {1}'.format(self.model_script, i)
                    os.system(join_model_script)
                else:
                    print('Unrecognized script type. Options are shell script (.sh) or python script (.py).')
                    sys.exit()

                if self.output_script is not None:
                    # Run output_script to extract output of interest from model output files.
                    if self.output_script.lower().endswith('.sh'):
                        join_output_script = './{0} {1}'.format(self.output_script, i)
                        os.system(join_output_script)
                    elif self.output_script.lower().endswith('.py'):
                        join_output_script = 'python {0} {1}'.format(self.output_script, i)
                        os.system(join_output_script)
                    else:
                        print('Unrecognized script type. Options are shell script (.sh) or python script (.py).')
                        sys.exit()

                    # Save the results from each simulation to a separate text file
                    self.QOI.append(np.loadtxt('UQpy_eval_{}.txt'.format(i)))

    ####################################################################################################################
    class RunParallel:

        """
        A subclass of RunModel to run a third-party software model with parallel processing.

        Most attributes of this subclass are inhereted from RunModel. The only variable that is not inherited is QOI.

        Input:
        :param samples: Inherited from RunModel. See its documentation.
        :type samples: numpy array

        :param dimension: Inherited from RunModel. See its documentation.
        :type dimension: int

        :param model_script: Inherited from RunModel. See its documentation.
        :type: model_script: str

        :param input_script: Inherited from RunModel. See its documentation.
        :type: input_script: str

        :param output_script: Inherited from RunModel. See its documentation.
        :type output_script: str

        Output:
        :param QOI: List containing the Quantity of Interest from the simulations
                    Each item in the list corresponds to one simulation
        :type QOI: list
                    Each item in the list may be of arbitrary data type (e.g. int, float, nparray, etc.)
        """

        # Authors: Dimitris Giovanis, Michael D. Shields
        # Updated: 5/1/18 by Michael D. Shields & Dimitris Giovanis

        def __init__(self, samples=None, cpu=None, model_script=None, input_script=None, output_script=None,
                     dimension=None):

            self.samples = samples
            self.dimension = dimension
            self.CPUs = cpu
            self.model_script = model_script
            self.input_script = input_script
            self.output_script = output_script

            from multiprocessing import Process
            from multiprocessing import Queue

            jobs_per_cpu = int(np.floor(self.samples.shape[0]/self.CPUs))
            jobs_remaining = np.mod(self.samples.shape[0],self.CPUs)
            if jobs_per_cpu == 0:
                self.CPUs = jobs_remaining
                print('The number of CPUs used is {}\n '.format(self.CPUs))

            # Break the simulation set into sets to be run over each CPU
            [batches, batch_ind] = self.chunk_samples_cpus()

            # Initialize the parallel processing queue and processes
            que = Queue()
            jobs = [Process(target=self.run_parallel_model, args=(batch_ind[a], que)) for a in
                    range(self.CPUs)]

            # Start the parallel processes.
            for j in jobs:
                j.start()
            for j in jobs:
                j.join()

            # Collect the results from the processes and sort them into the original sample order.
            self.QOI = [None]*self.samples.shape[0]
            results = [que.get(j) for j in jobs]
            for i in range(self.CPUs):
                k = 0
                for j in results[i][0]:
                    self.QOI[j] = results[i][1][k]
                    k = k+1

        ################################################################################################################
        # Function to call the model
        def run_parallel_model(self, job_inds, que):

            if self.samples.size == 1:
                self.samples = self.samples.reshape(1, 1)

            if len(self.samples.shape) == 1 and self.dimension != 1:
                self.samples = self.samples.reshape(1, self.samples.shape[0])
            elif len(self.samples.shape) == 1 and self.dimension == 1:
                self.samples = self.samples.reshape(self.samples.shape[0], 1)

            model_eval = list()
            for i in job_inds:

                # Write each value of UQpyOut.txt into a *.txt file
                np.savetxt('UQpy_run_{0}.txt'.format(int(i)), self.samples[i, :], newline=' ', delimiter=',',
                           fmt='%0.5f')

                # Run the input script to convert UQpy_run_X.txt to a valid model input
                if self.input_script.lower().endswith('.sh'):
                    join_input_script = './{0} {1}'.format(self.input_script, int(i))
                    os.system(join_input_script)
                else:
                    print('Unrecognized type of input file script. Must be .sh')
                    sys.exit()

                # Run the third-party model script (model_script)
                if self.model_script.lower().endswith('.sh'):
                    join_model_script = './{0} {1}'.format(self.model_script, int(i))
                    os.system(join_model_script)
                else:
                    print('Unrecognized type of model file')
                    sys.exit()

                # Run the output script to convert model results to UQpy_eval_X.txt to be read by UQpy
                if self.output_script.lower().endswith('.sh'):
                    join_output_script = './{0} {1}'.format(self.output_script, int(i))
                    os.system(join_output_script)
                else:
                    print('Unrecognized type of Input file')
                    sys.exit()

                model_eval.append(np.loadtxt('UQpy_eval_{0}.txt'.format(int(i))))

                src_files = 'UQpy_eval_{0}.txt'.format(int(i))
                file_new = src_files.replace("UQpy_eval_{0}.txt".format(int(i)), "Model_{0}.txt".format(int(i)))
                os.rename(src_files, file_new)

            model_eval = que.put([job_inds, model_eval])

            return model_eval

        ################################################################################################################
        # Chunk the samples into batches
        def chunk_samples_cpus(self):

            size_ = np.array([np.ceil(self.samples.shape[0]/self.CPUs) for i in range(self.CPUs)]).astype(int)
            dif = np.sum(size_) - self.samples.shape[0]
            for k in range(dif):
                size_[k] = size_[k] - 1
            batches = [None]*self.CPUs
            batch_ind = [None]*self.CPUs
            for i in range(self.CPUs):
                if i == 0:
                    batch_ind[i] = range(size_[i])
                else:
                    batch_ind[i] = range(int(np.sum(size_[:i])), int(np.sum(size_[:i+1])))
                batches[i] = self.samples[batch_ind[i], :]
            return batches, batch_ind

        # This code may be used in the future to extend for distributed computing for HPC use.
        # def chunk_samples_nodes(samples, args):
        #
        #     # In case of cluster divide the samples into chunks in order to sent to each processor
        #     chunks = args.nodes
        #     size = np.array([np.ceil(samples.shape[0]/chunks) in range(args.nodes)]).astype(int)
        #     dif = np.sum(size) - samples.shape[0]
        #     count = 0
        #     for k in range(dif):
        #         size[count] = size[count] - 1
        #         count = count + 1
        #     for i in range(args.nodes):
        #         if i == 0:
        #             lines = range(0, size[i])
        #         else:
        #             lines = range(int(np.sum(size[:i])), int(np.sum(size[:i+1])))
        #
        #         np.savetxt('UQpy_Batch_{0}.txt'.format(i+1), samples[lines, :],  fmt='%0.5f')
        #         np.savetxt('UQpy_Batch_index_{0}.txt'.format(i+1), lines)