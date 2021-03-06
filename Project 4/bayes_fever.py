import random
from matplotlib import pyplot as plt


class BooleanVariableNode(object):
    """Class representing a single node in a Bayesian network.

    The conditional probability table (CPT) is stored as a dictionary, keyed by tuples of parent
    node values.
    """

    def __init__(self, var, parent_vars, cpt_entries):
        """Constuctor for node class.

        Args:
            var: string variable name
            parent_vars: a sequence of strings specifying the parent variable names
            cpt_entries: a dictionary specifying the CPT, keyed by a tuple of parent values, 
                with values specifying the prob that this variable=true
        """
        self.parents = parent_vars
        self.target = var
        self.cpt = cpt_entries  # (parent_val1, parent_val2, ...) => prob

    def get_parents(self):
        return self.parents
    
    def get_var(self):
        return self.target

    def get_prob_true(self, parent_vals):
        key = tuple(parent_vals)
        return self.cpt[key]

    def get_prob_false(self, parent_vals):
        return 1.0 - self.get_prob_true(parent_vals)


class SimpleSampler(object):
    """Sampler that generates samples with no evidence."""
    
    def __init__(self, nodes):
        self.nodes = nodes
    
    def generate_sample(self):
        """Create a single sample instance, returns a dictionary."""
        sample_vals = {}  # variable => value
        while len(sample_vals) < len(self.nodes):       
            for node in self.nodes:
                var = node.get_var()
                if node not in sample_vals:  # we haven't generated a value for this var
                    parent_vars = node.get_parents()
                    if all([ p in sample_vals for p in parent_vars ]):  # all parent vals generated
                        parent_vals = tuple([ sample_vals[par] for par in parent_vars ])
                        prob_true = node.get_prob_true(parent_vals)
                        sample_vals[var] = random.random() < prob_true
        return sample_vals
        
    def generate_samples(self, n):
        """Create multiple samples, returns a list of dictionaries."""
        return [ self.generate_sample() for x in range(n) ]
    
    def get_prob(self, query_vals, num_samples):
        """Return the (joint) probability of the query variables.
        
        Args:
            query_vals: dictionary mapping { variable => value }
            num_samples: number of simple samples to generate for the calculation

        Returns: empirical probability of query values
        """
        
        samples = self.generate_samples(num_samples)  # generate samples
        count = 0  # initialize count variable
        
        for dictionary in samples:  # iterate through each sample (dictionary)
            if all((k in dictionary and dictionary[k] == v) for k,v in query_vals.items()): count += 1  # increment if query_val key is in dict and if dict[key] = query_val[key]     
        return count / num_samples  # return probability

        
class RejectionSampler(SimpleSampler):
    """Sampler that generates samples given evidence using rejection sampling."""

    def generate_samples(self, n, evidence_vals={}):
        """Return simple samples that agree with evidence (may be less than n)."""
        unfiltered = super().generate_samples(n)
        keeps = []
        for sample in unfiltered:  # get rid of anything that doesn't match the evidence
            if all(sample.get(var, None) == val for var, val in evidence_vals.items()):
                keeps.append(sample)
        return keeps

    def get_prob(self, query_vals, evidence_vals, num_samples):
        """Return the conditional probability of the query variables, given evidence.
        
        Args:
            query_vals: dictionary mapping { variable => value }
            num_samples: number of simple samples to generate for the calculation (the number
                "kept" that agree with evidence will be significantly lower)

        Returns: empirical conditional probability of query values given evidence
        """
        
        samples = self.generate_samples(num_samples, evidence_vals)  # generate samples, pass in evidence vals too
        count = 0  # initialize count variable
        
        for dictionary in samples:  # iterate through each sample (dictionary)
            if all((k in dictionary and dictionary[k] == v) for k,v in query_vals.items()): count += 1  # increment if query_val key is in dict and if dict[key] = query_val[key]
            
        return count / len(samples)  # return probability

class LikelihoodWeightingSampler(SimpleSampler):
    """Sampler that generates samples given evidence using likelihood weighting."""

    def generate_sample(self, evidence_vals):
        """Create a single sample instance that agrees with evidence.
        
        Returns a dictionary containing the sample and the corresponding weight."""
        sample_vals = {}  # variable => value
        weight = 1.0

        while len(sample_vals) < len(self.nodes):    
            for node in self.nodes:
                var = node.get_var()
                if node not in sample_vals:
                    parent_vars = node.get_parents()
                    if all([ p in sample_vals for p in parent_vars ]):
                        parent_vals = tuple([ sample_vals[par] for par in parent_vars ])
                        if var in evidence_vals:  # if evidence, adjust the weight by the likelihood
                            val = evidence_vals[var]
                            sample_vals[var] = val
                            p = node.get_prob_true(parent_vals) if val else node.get_prob_false(parent_vals)
                            weight *= p
                        else:  # generate a value using the CPT
                            prob_true = node.get_prob_true(parent_vals)
                            sample_vals[var] = random.random() < prob_true
        return sample_vals, weight

    def generate_samples(self, n, evidence_vals={}):
        """Create multiple samples, returns a list of dictionary/weight tuples."""
        return [ self.generate_sample(evidence_vals) for x in range(n) ]

    def get_prob(self, query_vals, evidence_vals, num_samples):
        """Return the conditional probability of the query variables, given evidence.
        
        Args:
            query_vals: dictionary mapping { variable => value }
            num_samples: number of simple samples to generate for the calculation 

        Returns: empirical conditional probability of query values given evidence
        """
        
        samples = self.generate_samples(num_samples, evidence_vals)  # generate samples and pass in evidence vals
        count,count2 = 0,0  # initialize both counts
        
        for toople in samples:  # iterate through each tuple in samples - each toople is (dictionary, float)
            count2 += toople[1]  # increment count 2 (probability denominator) by tuple's weight (float)
            if all((k in toople[0] and toople[0][k] == v) for k,v in query_vals.items()): count += toople[1]  # if key in dict and dict[key] = query_vals[key], count += weight
            
        return count / count2  # return probability


def bayes_sample_size_plot(sampler1, sampler2, query, evidence, label1, label2, title, fname):
    """Create a plot comparing approximate value of a conditional probability for two samplers.

    Args:
        sampler1: first approximate sampler to compare
        sampler2: second approximate sampler to compare
        query: dict of form { node => value } for all query nodes
        evidence: dict of form { node => value } for all evidence nodes
        label1: plot label for first sampler
        label2: plot label for second sampler
        title: plot title
        fname: path of output pdf   
    """
    
    a1,a2 = [],[]  # initialize yaxis values for sampler1, sampler2
    
    for i in range(20,10000,100):  # each number of samples to test for
        samples1, samples2, count, count2 = sampler1.generate_samples(i, evidence), sampler2.generate_samples(i, evidence), 0, 0  # intitialize samples and counts
        
        for dictionary in samples1:  # iterate through each sample (dictionary)
                if all((k in dictionary and str(dictionary[k]) == str(v)) for k,v in query.items()): count += 1  # increment count if valid
        a1.append(count / len(samples1))  # add yaxis value to a1
                
        count = 0  # reinitialize count
        
        for toople in samples2:  # iterate through each tuple (dictionary, float)
            count2 += toople[1]  # increment count 2 (probability denominator) by tuple's weight (float)
            if all((k in toople[0] and toople[0][k] == v) for k,v in query.items()): count += toople[1]  # if key in dict and dict[key] = query_vals[key], count += weight
        a2.append(count / count2)  # add yaxis value to a2
    
    xaxis = [i for i in range(20,10000,100)]  # set xaxis to list of each # of samples we tested 
    two_line_plot(xaxis, a1, "sampler1", xaxis, a2, "sampler2", "Sampler1 vs. Sampler2", "383fig.pdf")  # call two_line_plot to generate
    return


def two_line_plot(xvals1, yvals1, label1, xvals2, yvals2, label2, title, outfile_path):
    """Create a line chart comparing two data series and save it as a pdf.
    
    Args:
        xvals1: x-values for series 1
        yvals1: y-values for series 1
        label1: label for series 1
        xvals2: x-values for series 2
        yvals2: y-values for series 2
        label2: label for series 2
        title: plot title
        outfile_path: filename to save plot
    """
    plt.plot(xvals1, yvals1, label=label1, color='blue', marker='.', linestyle='solid')
    plt.plot(xvals2, yvals2, label=label2, color='green', marker='.', linestyle='solid')
    plt.title(title)
    plt.legend()
    plt.savefig(outfile_path)


##########################################

if __name__ == '__main__':

    # The conditional probabilities below must be replaced by the actual values
    # learned from data!
    FEVER_NODES = [
        BooleanVariableNode('E', (),     {(): 0.25}),
        BooleanVariableNode('F', ('E',), {(True,): 0.5, (False,): 0.1}),
        BooleanVariableNode('A', ('F',), {(True,): 0.875, (False,): 0.25}),
        BooleanVariableNode('T', ('F',), {(True,): 0.75, (False,): 0.0625}),
    ]
    sampler_simp = SimpleSampler(FEVER_NODES)
    sampler_reject = RejectionSampler(FEVER_NODES)
    sampler_like = LikelihoodWeightingSampler(FEVER_NODES)

    n = 10000  # the number of samples to generate

    # estimate the quantities calculated previously
    inference_probs = [
        ("a. P(enrolled)", {'E': True}, {}),
        ("b. P(test)", {'T': True}, {}),
        ("c. P(awesome)", {'A': True}, {}),
        ("d. P(awesome, test)", {'A': True, 'T': True}, {}),
        ("f. P(enrolled | awesome)", {'E': True}, {'A': True}),
        ("g. P(enrolled | awesome, test)", {'E': True}, {'A': True, 'T': True}),    
    ]
    for label, query, evidence in inference_probs:
        print(label)
        if not evidence:
            print("simple:     {:.4f}".format(sampler_simp.get_prob(query, n)))
        print("rejection:  {:.4f}".format(sampler_reject.get_prob(query, evidence, n)))
        print("likelihood: {:.4f}\n".format(sampler_like.get_prob(query, evidence, n)))
        print("")

    # plot some approximate probabilities as a function of the number of samples
    bayes_sample_size_plot(sampler_reject, sampler_like, 
                           {'E': True}, {'A': True, 'T': True}, 
                           "rejection", "likelihood weighting", "P(e | a, t) vs n", 
                           "bayes_fever.pdf")
