import sys
from pylab import *
import numpy as np
from scipy.io import loadmat
from sklearn.neighbors import KNeighborsClassifier
from sklearn import cross_validation
from multiprocessing import Pool
from sklearn.pipeline import Pipeline
from sklearn.feature_selection import RFECV
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import MultinomialNB
from sklearn.cross_validation import StratifiedKFold
from sklearn import preprocessing
from sklearn.feature_selection import SelectKBest
from sklearn.feature_selection import chi2


class Data(object):
    def __init__(self):
        self.mat_data = loadmat('letter.mat')
        self.y = np.matrix(self.mat_data['classlabel'].T)
        self.X = np.matrix(self.mat_data['X'])
        self.attributeNames = [
            n[0] for n in self.mat_data['attributeNames'][0]]
        self.N, self.M = self.X.shape

        # Add offset attribute
        self.X = np.concatenate((np.ones((self.X.shape[0], 1)), self.X), 1)
        self.attributeNames = [u'Offset']+self.attributeNames
        self.M = self.M+1


class KNeighbors(object):
    def __init__(self, max_k=8, internal_cross=4, p=2):
        self.max_k = max_k
        self.internal_cross = internal_cross
        self.p = p

    def __get_best_k(self, X, y):
        n, m = X.shape
        cv = cross_validation.KFold(n, self.internal_cross)
        inner_errors = np.zeros((self.internal_cross, self.max_k))
        j = 0
        for train_index, test_index in cv:
            X_train = X[train_index, :]
            y_train = y[train_index, :]
            X_test = X[test_index, :]
            y_test = y[test_index, :]
            for l in range(0, self.max_k):
                knclassifier = KNeighborsClassifier(n_neighbors=l+1, p=self.p)
                knclassifier.fit(X_train, ravel(y_train))
                y_est = knclassifier.predict(X_test)
                inner_errors[j, l] = \
                    np.sum(ravel(y_est) != ravel(y_test)) / float(len(X_test))
            j += 1
        errors = sum(inner_errors, 0) / float(self.internal_cross)
        print "error rates: ", errors
        sys.stdout.flush()
        return errors.argmin() + 1

    def run(self, fold, X_train, y_train, X_test, y_test):
        best_k = self.__get_best_k(X_train, y_train)
        knclassifier = KNeighborsClassifier(n_neighbors=best_k, p=2)
        knclassifier.fit(X_train, ravel(y_train))
        y_est = knclassifier.predict(X_test)
        print "KNeighbors fold ", fold, " done!"
        return np.sum(ravel(y_est) != ravel(y_test)) / float(len(X_test))

    def __call__(self, fold, X_train, y_train, X_test, y_test):
        return self.run(fold, X_train, y_train, X_test, y_test)


class NaiveBayes(object):
    def __init__(self, alpha=1.0, est_prior=True, internal_cross=5):
        self.alpha = alpha
        self.est_prior = est_prior
        self.internal_cross = internal_cross

    def run(self, fold, X_train, y_train, X_test, y_test):
        nb_classifier = MultinomialNB(alpha=self.alpha, fit_prior=self.est_prior)
        le = preprocessing.LabelEncoder()
        le.fit_transform(ravel(y_train))

        feature_selector = RFECV(
            estimator=nb_classifier,
            step=1,
            cv=StratifiedKFold(ravel(y_train), self.internal_cross),
            scoring='accuracy'
            )

        classifier = Pipeline([
            ('feature_selection', feature_selector),
            ('classification', nb_classifier)
            ])

        classifier.fit(X_train, le.transform(ravel(y_train)))
        result = classifier.predict(X_test)
        y_est = le.inverse_transform(result)

        print "KNeighbors fold ", fold, " done!"
        error_sum = np.sum(ravel(y_est) != ravel(y_test))
        return error_sum / float(len(X_test))

    def __call__(self, fold, X_train, y_train, X_test, y_test):
        return self.run(fold, X_train, y_train, X_test, y_test)


def main():
    np.set_printoptions(edgeitems=7)
    data = Data()
    K = 10  # K-fold crossvalidation
    N = 2  # number of classification algorithms
    CV = cross_validation.KFold(data.N, K)
    k_neighbours = KNeighbors()
    naive_bayes = NaiveBayes()
    errors = np.zeros((N, K))
    pool = Pool(K*N)
    responses = {}
    i = 0
    for train_index, test_index in CV:
        X_train = data.X[train_index, :]
        y_train = data.y[train_index, :]
        X_test = data.X[test_index, :]
        y_test = data.y[test_index, :]
        responses[i, 0] = pool.apply_async(
            k_neighbours,
            args=(i, X_train, y_train, X_test, y_test)
            )
        responses[i, 1] = pool.apply_async(
            naive_bayes,
            args=(i, X_train, y_train, X_test, y_test)
            )
        i += 1
    errors[0] = map((lambda x: responses[x, 0].get()), range(0, K))
    errors[1] = map((lambda x: responses[x, 1].get()), range(0, K))
    print "k-neighbours error rates: \n", "\t\t", errors[0], "\naverage: ", np.average(errors[0])
    print "naive bayes error rates: \n", "\t\t", errors[1], "\naverage: ", np.average(errors[1])
    pool.close()
    pool.join()
    return


if __name__ == '__main__':
    main()
